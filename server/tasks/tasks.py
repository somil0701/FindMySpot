# server/tasks/tasks.py
from dotenv import load_dotenv
import os
import csv
from datetime import datetime
from celery import Celery
import os.path as path
from datetime import timedelta
from calendar import monthrange
from celery.schedules import crontab
import smtplib
from email.message import EmailMessage
import mimetypes

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

# broker/backend (Redis) from env or default
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

celery = Celery(
    "parking_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

# Export directory (override with EXPORT_DIR env var if desired)
EXPORT_DIR = os.environ.get('EXPORT_DIR', path.join(PROJECT_ROOT, "exports"))

# SMTP / Email configuration (read from .env)
SMTP_HOST = os.environ.get('SMTP_HOST')
SMTP_PORT = int(os.environ.get('SMTP_PORT') or 587)
SMTP_USER = os.environ.get('SMTP_USER')
SMTP_PASS = os.environ.get('SMTP_PASS')
FROM_EMAIL = os.environ.get('FROM_EMAIL') or SMTP_USER
FROM_NAME = os.environ.get('FROM_NAME', 'ParkEZ')

# Helper: ensure export dir exists
def ensure_export_dir():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    return EXPORT_DIR


# ---------------------------
# Email helper
# ---------------------------

def send_email_with_attachment(smtp_host, smtp_port, smtp_user, smtp_pass, from_addr, to_addr, subject, body_text, attachment_path, attachment_name=None):
    """
    Send an email with an optional file attachment using STARTTLS (port 587).
    Returns (True, info) on success or (False, str) on failure.
    This version safely handles attachment_path being None.
    """
    # minimal config check: for debug SMTP hosts you may not require smtp_user/smtp_pass
    if not smtp_host or not from_addr:
        return (False, "smtp configuration incomplete")

    if not to_addr:
        return (False, "missing recipient")

    # derive attachment_name safely only if attachment_path is provided
    final_attachment_name = None
    if attachment_name:
        final_attachment_name = attachment_name
    elif attachment_path:
        try:
            final_attachment_name = os.path.basename(attachment_path)
        except Exception:
            final_attachment_name = None

    try:
        # build message
        msg = EmailMessage()
        msg["From"] = f"{FROM_NAME} <{from_addr}>"
        msg["To"] = to_addr
        msg["Subject"] = subject or ""
        msg.set_content(body_text or "")

        # attach file if provided and exists
        if attachment_path:
            try:
                if os.path.exists(attachment_path) and os.path.isfile(attachment_path):
                    ctype, encoding = mimetypes.guess_type(attachment_path)
                    if ctype is None or encoding is not None:
                        ctype = "application/octet-stream"
                    maintype, subtype = ctype.split('/', 1)
                    with open(attachment_path, 'rb') as fh:
                        file_data = fh.read()
                        msg.add_attachment(file_data, maintype=maintype, subtype=subtype, filename=(final_attachment_name or os.path.basename(attachment_path)))
                else:
                    # file missing — append note to body instead of failing
                    msg.set_content((body_text or "") + "\n\n(Note: attachment not found on server)")
            except Exception as e:
                msg.set_content((body_text or "") + f"\n\n(Note: failed to attach file: {e})")

        # connect and send
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
        try:
            server.ehlo()
            # try STARTTLS for common ports (will be ignored/harmless on some debug servers)
            if smtp_port in (587, 25):
                try:
                    server.starttls()
                    server.ehlo()
                except Exception:
                    pass
            # attempt login only if credentials provided (if they fail, continue)
            try:
                if smtp_user and smtp_pass:
                    server.login(smtp_user, smtp_pass)
            except Exception:
                pass
            server.send_message(msg)
        finally:
            try:
                server.quit()
            except Exception:
                pass

        return (True, "sent")
    except Exception as e:
        return (False, str(e))


@celery.task(bind=True)
def export_reservations_csv_task(self, user_id):
    """
    Generate CSV for a user's reservations and return metadata.
    Result stored in Celery backend: {"filename": "...", "filepath": "..."}
    """
    # import create_app lazily to avoid circular imports at module import time
    from server.app import create_app

    app = create_app()
    with app.app_context():
        from server.models.reservation import Reservation
        from server.models.spot import ParkingSpot
        from server.models.lot import ParkingLot

        ensure_export_dir()

        resvs = Reservation.query.filter_by(user_id=user_id).order_by(Reservation.start_time.asc()).all()

        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        filename = f"user_{user_id}_reservations_{ts}.csv"
        filepath = os.path.join(EXPORT_DIR, filename)

        with open(filepath, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["reservation_id","lot_id","lot_name","spot_id","spot_number","start_time","end_time","duration_seconds","cost","remarks"])
            for r in resvs:
                spot = ParkingSpot.query.get(r.spot_id) if r.spot_id else None
                lot = ParkingLot.query.get(spot.lot_id) if (spot and getattr(spot, "lot_id", None)) else None

                start_iso = r.start_time.isoformat() if r.start_time else ""
                end_iso = r.end_time.isoformat() if r.end_time else ""
                duration = ""
                try:
                    if r.start_time and r.end_time:
                        duration = int((r.end_time - r.start_time).total_seconds())
                except Exception:
                    duration = ""

                remarks = getattr(r, "notes", None) or ""

                writer.writerow([
                    r.id,
                    getattr(lot, "id", ""),
                    getattr(lot, "name", ""),
                    getattr(spot, "id", ""),
                    getattr(spot, "number", ""),
                    start_iso,
                    end_iso,
                    duration,
                    getattr(r, "cost", ""),
                    remarks
                ])

        # Return metadata so status endpoint can expose download link
        return {"filename": filename, "filepath": filepath}


# ---------------------------
# Monthly report task
# ---------------------------

def render_pdf_from_html(html_content, out_path):
    """
    Try to render PDF using WeasyPrint. If weasyprint is not installed or
    rendering fails, raise to let caller fallback.
    """
    try:
        from weasyprint import HTML
    except Exception as e:
        raise RuntimeError("WeasyPrint not available: " + str(e))

    # render
    HTML(string=html_content).write_pdf(out_path)
    return out_path

def build_monthly_report_html(user, year, month, reservations, totals):
    """
    Build a simple but clean HTML page for the monthly report.
    'reservations' is a list of dict rows, 'totals' is computed stats.
    """
    month_name = f"{year}-{month:02d}"
    css = """
    <style>
      body { font-family: Arial, Helvetica, sans-serif; padding: 20px; color: #222; }
      h1 { color: #1f6feb; }
      table { width: 100%; border-collapse: collapse; margin-top: 18px; }
      th, td { border: 1px solid #ddd; padding: 8px; font-size: 13px; }
      th { background: #f7f7f7; text-align: left; }
      .summary { margin-top: 10px; }
      .small { font-size: 12px; color: #666; }
    </style>
    """

    rows_html = ""
    for r in reservations:
        rows_html += f"<tr>" \
                     f"<td>{r.get('id','')}</td>" \
                     f"<td>{r.get('lot_name','')}</td>" \
                     f"<td>{r.get('spot_number','')}</td>" \
                     f"<td>{r.get('start_time','')}</td>" \
                     f"<td>{r.get('end_time','')}</td>" \
                     f"<td>{r.get('duration_seconds','')}</td>" \
                     f"<td>{r.get('cost','')}</td>" \
                     f"</tr>"

    html = f"""
    <html>
      <head><meta charset="utf-8"/>{css}</head>
      <body>
        <h1>ParkEZ — Monthly Activity Report</h1>
        <div class="small">User: {user.username} ({user.email})</div>
        <div class="small">Period: {month_name}</div>

        <div class="summary">
          <p><strong>Total reservations:</strong> {totals.get('total_reservations',0)} &nbsp; 
          <strong>Total hours:</strong> {totals.get('total_hours',0)} &nbsp;
          <strong>Total spent:</strong> {totals.get('total_spent',0)}</p>

          <p><strong>Most used lot:</strong> {totals.get('most_used_lot','-')}</p>
        </div>

        <table>
          <thead>
            <tr>
              <th>Reservation</th><th>Lot</th><th>Spot</th><th>Start</th><th>End</th><th>Seconds</th><th>Cost</th>
            </tr>
          </thead>
          <tbody>
            {rows_html}
          </tbody>
        </table>

        <p class="small">Generated: {datetime.utcnow().isoformat()} UTC</p>
      </body>
    </html>
    """
    return html

@celery.task(bind=True)
def monthly_report_task(self, user_id, year=None, month=None, prefer_pdf=True):
    """
    Generate monthly report for a user and email it.
    If prefer_pdf is True and PDF generation is available, send a PDF.
    Otherwise fall back to HTML attachment.

    Returns a dict with metadata about what was generated and email result.
    """
    # import create_app lazily to avoid circular imports at module import time
    from server.app import create_app

    app = create_app()
    with app.app_context():
        try:
            from server.models.reservation import Reservation
            from server.models.spot import ParkingSpot
            from server.models.lot import ParkingLot
            from server.models.user import User
            import sqlalchemy
        except Exception as e:
            raise

        # determine target month (previous month if not provided)
        # today = datetime.utcnow().date()
        # if year is None or month is None:
        #     # previous month
        #     first_of_this_month = today.replace(day=1)
        #     prev_last_day = first_of_this_month - timedelta(days=1)
        #     target_year = prev_last_day.year
        #     target_month = prev_last_day.month
        # else:
        #     target_year = int(year)
        #     target_month = int(month)

        today = datetime.utcnow().date()
        if year is None or month is None:
            # default to current month instead of previous month
            target_year = today.year
            target_month = today.month
        else:
            target_year = int(year)
            target_month = int(month)


        # compute date range
        start_date = datetime(target_year, target_month, 1)
        last_day = monthrange(target_year, target_month)[1]
        end_date = datetime(target_year, target_month, last_day, 23, 59, 59)

        user = User.query.get(user_id)
        if not user:
            return {"error": "user_not_found"}

        # fetch reservations in the month
        resvs = Reservation.query.filter(
            Reservation.user_id == user_id,
            Reservation.start_time >= start_date,
            Reservation.start_time <= end_date
        ).order_by(Reservation.start_time.asc()).all()

        # prepare rows and totals
        rows = []
        totals = {"total_reservations": 0, "total_hours": 0, "total_spent": 0.0, "lot_counts": {}}
        for r in resvs:
            spot = ParkingSpot.query.get(r.spot_id) if r.spot_id else None
            lot = ParkingLot.query.get(spot.lot_id) if (spot and getattr(spot,"lot_id",None)) else None
            start_iso = r.start_time.isoformat() if r.start_time else ""
            end_iso = r.end_time.isoformat() if r.end_time else ""
            duration = None
            try:
                if r.start_time and r.end_time:
                    duration = int((r.end_time - r.start_time).total_seconds())
                    totals["total_hours"] += (duration/3600.0)
            except Exception:
                duration = None

            cost = getattr(r, "cost", 0) or 0.0
            totals["total_spent"] += float(cost or 0)
            lot_name = getattr(lot, "name", "") if lot else ""
            lot_id = getattr(lot, "id", "") if lot else ""

            totals["lot_counts"][lot_name or f"lot_{lot_id}"] = totals["lot_counts"].get(lot_name or f"lot_{lot_id}", 0) + 1

            rows.append({
                "id": r.id,
                "lot_name": lot_name,
                "spot_number": getattr(spot, "number", ""),
                "start_time": start_iso,
                "end_time": end_iso,
                "duration_seconds": duration,
                "cost": cost
            })

        totals["total_reservations"] = len(rows)
        # find most used lot
        most_used = None
        if totals["lot_counts"]:
            most_used = max(totals["lot_counts"].items(), key=lambda kv: kv[1])[0]
        totals["most_used_lot"] = most_used

        # build HTML
        html = build_monthly_report_html(user, target_year, target_month, rows, totals)

        # file names
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        filename_base = f"user_{user_id}_monthly_report_{target_year}{target_month:02d}_{ts}"
        pdf_path = os.path.join(EXPORT_DIR, f"{filename_base}.pdf")
        html_path = os.path.join(EXPORT_DIR, f"{filename_base}.html")

        # ensure export dir
        ensure_export_dir()

        # save HTML
        with open(html_path, "w", encoding="utf-8") as fh:
            fh.write(html)

        created_file = None
        created_type = None
        # try render PDF if preferred
        if prefer_pdf:
            try:
                render_pdf_from_html(html, pdf_path)
                created_file = pdf_path
                created_type = "pdf"
            except Exception as e:
                # fallback to HTML attachment
                created_file = html_path
                created_type = "html"
        else:
            created_file = html_path
            created_type = "html"

        # Send email if SMTP configured
        notify_results = {"email": None, "created_type": created_type, "created_path": created_file}
        try:
            user_email = getattr(user, "email", None)
            if SMTP_HOST and user_email and created_file:
                subject = f"ParkEZ Monthly Report — {target_year}-{target_month:02d}"
                body = f"Hello {getattr(user,'username','')},\n\nPlease find attached your monthly ParkEZ activity report for {target_year}-{target_month:02d}.\n\nRegards,\nParkEZ"

                ok, info = send_email_with_attachment(
                    smtp_host=SMTP_HOST,
                    smtp_port=SMTP_PORT,
                    smtp_user=SMTP_USER,
                    smtp_pass=SMTP_PASS,
                    from_addr=FROM_EMAIL,
                    to_addr=user_email,
                    subject=subject,
                    body_text=body,
                    attachment_path=created_file,
                    attachment_name=os.path.basename(created_file)
                )
                notify_results["email"] = {"ok": ok, "info": info, "to": user_email}
            else:
                notify_results["email"] = {"ok": False, "info": "SMTP_HOST or user_email or attachment missing"}
        except Exception as e:
            notify_results["email"] = {"ok": False, "info": str(e)}

        # Return metadata
        return {
            "user_id": user_id,
            "period": f"{target_year}-{target_month:02d}",
            "file": os.path.basename(created_file) if created_file else None,
            "created_type": created_type,
            "notifications": notify_results
        }


@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # run a job on 1st day of each month at 00:05 UTC which enqueues monthly_report_task for each user
    sender.add_periodic_task(
        crontab(minute=5, hour=0, day_of_month='1'),
        enqueue_monthly_reports.s(),
        name='enqueue_monthly_reports_on_1st'
    )


@celery.task(bind=True)
def enqueue_monthly_reports(self):
    """
    Enqueue monthly_report_task for every user in the system.
    This is a single scheduled job that creates tasks for each user.
    """
    # import create_app lazily to avoid circular import during module load
    from server.app import create_app

    app = create_app()
    with app.app_context():
        try:
            from server.models.user import User
        except Exception:
            raise

        users = User.query.all()
        for u in users:
            # enqueue a per-user monthly report (previous month)
            monthly_report_task.delay(u.id)

# ---------------------------
# Daily reminder task
# ---------------------------

from datetime import datetime, timedelta

@celery.task(bind=True)
def send_daily_reminder(self, cutoff_days=7, hour_to_send=18):
    """
    Send a daily reminder email to users who haven't visited recently.

    Arguments:
      cutoff_days (int): consider users who have not had a reservation in this many days.
      hour_to_send (int): hour of day used in scheduling (this param isn't used
                          inside the task but is exposed for clarity / testing).
    Returns:
      dict summary with list of emails that were attempted.
    """
    # Import app and models lazily to avoid circular imports at module load time
    from server.app import create_app
    from server.models.user import User
    from server.models.reservation import Reservation

    app = create_app()
    with app.app_context():
        try:
            cutoff = datetime.utcnow() - timedelta(days=int(cutoff_days or 7))
        except Exception:
            cutoff = datetime.utcnow() - timedelta(days=7)

        notified = []
        skipped_no_email = []
        candidates = []

        # Iterate users to determine eligibility
        users = User.query.all()
        for u in users:
            # skip admin accounts if role is admin
            if getattr(u, 'role', None) == 'admin':
                continue

            last_res = Reservation.query.filter_by(user_id=u.id).order_by(Reservation.start_time.desc()).first()
            # If user never reserved OR last reservation older than cutoff => candidate
            if (not last_res) or (last_res and last_res.start_time < cutoff):
                candidates.append(u)

        # If SMTP is configured, send emails; otherwise return the candidate list for inspection
        global SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, FROM_EMAIL, FROM_NAME
        smtp_ok = SMTP_HOST and SMTP_USER and SMTP_PASS and FROM_EMAIL

        # Email body template
        subject = "ParkEZ — Reminder: Book parking if you need it"
        body_template = (
            "Hello {username},\n\n"
            "We noticed you haven't parked with ParkEZ recently. If you need a parking spot, "
            "you can visit the ParkEZ dashboard to find and reserve an available spot.\n\n"
            "Regards,\nParkEZ Team"
        )

        for u in candidates:
            to_addr = getattr(u, "email", None)
            if not to_addr:
                skipped_no_email.append({'user_id': u.id, 'username': getattr(u, 'username', None)})
                continue

            # If no SMTP configured, don't attempt sending; just record candidate
            if not smtp_ok:
                notified.append({'user_id': u.id, 'email': to_addr, 'sent': False, 'reason': 'smtp_not_configured'})
                continue

            # Try sending email (using existing helper). It returns (ok, info)
            try:
                ok, info = send_email_with_attachment(
                    smtp_host=SMTP_HOST,
                    smtp_port=SMTP_PORT,
                    smtp_user=SMTP_USER,
                    smtp_pass=SMTP_PASS,
                    from_addr=FROM_EMAIL,
                    to_addr=to_addr,
                    subject=subject,
                    body_text=body_template.format(username=getattr(u, 'username', 'User')),
                    attachment_path=None,  # no attachment for reminder
                    attachment_name=None
                )

                notified.append({'user_id': u.id, 'email': to_addr, 'sent': bool(ok), 'info': info})
            except Exception as e:
                notified.append({'user_id': u.id, 'email': to_addr, 'sent': False, 'info': str(e)})

        # Return summary so AsyncResult.result contains helpful data
        return {
            'cutoff_days': int(cutoff_days),
            'num_users_total': len(users),
            'num_candidates': len(candidates),
            'notified': notified,
            'skipped_no_email': skipped_no_email
        }


# ---------------------------
# Register periodic schedules (including daily reminder)
# ---------------------------

from celery.schedules import crontab

@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """
    Register scheduled tasks:
      - daily reminder: every day at 18:00 UTC (configurable)
      - enqueue_monthly_reports: ran by existing schedule (1st of month)
    """
    # Daily reminder: run each day at 18:00 UTC (change hour/minute below as needed)
    # Use crontab(hour=18, minute=0) for 18:00 UTC daily
    sender.add_periodic_task(
        crontab(hour=18, minute=0),
        send_daily_reminder.s(),
        name='daily-reminder'
    )

    # Keep existing monthly enqueue task registration (if present)
    try:
        sender.add_periodic_task(
            crontab(minute=5, hour=0, day_of_month='1'),
            enqueue_monthly_reports.s(),
            name='enqueue_monthly_reports_on_1st'
        )
    except Exception:
        # If enqueue_monthly_reports not defined / imported yet, ignore here.
        pass
