# scripts/trigger_monthly_report.py
from server.tasks.tasks import monthly_report_task
import sys

if len(sys.argv) < 2:
    print("Usage: python scripts/trigger_monthly_report.py <user_id> [prefer_pdf]")
    sys.exit(1)

user_id = int(sys.argv[1])
prefer_pdf = True
if len(sys.argv) > 2:
    prefer_pdf = sys.argv[2].lower() not in ("0", "false", "no")

job = monthly_report_task.delay(user_id, prefer_pdf=prefer_pdf)
print("Dispatched monthly_report_task. Celery job id:", job.id)
