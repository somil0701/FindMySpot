# server/controllers/export.py
import os
from flask import Blueprint, request, jsonify, send_from_directory, current_app, abort
from ._auth_utils import token_required

export_bp = Blueprint('export', __name__)

@export_bp.route('/<int:user_id>', methods=['POST'])
@token_required
def export_csv(user_id):
    """
    Start asynchronous CSV export for a user. Returns task_id (202).
    """
    try:
        # lazy import the task to avoid circular imports
        from server.tasks.tasks import export_reservations_csv_task
    except Exception as e:
        current_app.logger.exception("Failed to import tasks: %s", e)
        return jsonify({'error': 'tasks_unavailable', 'message': str(e)}), 500

    job = export_reservations_csv_task.delay(user_id)
    return jsonify({'task_id': job.id}), 202


@export_bp.route('/status/<task_id>', methods=['GET'])
@token_required
def export_status(task_id):
    """
    Return Celery task status and download_url when ready.
    """
    try:
        from server.tasks.tasks import celery, EXPORT_DIR  # celery AsyncResult used to fetch task status
    except Exception as e:
        current_app.logger.exception("Failed to import celery: %s", e)
        return jsonify({'error': 'tasks_unavailable', 'message': str(e)}), 500

    async_result = celery.AsyncResult(task_id)
    state = async_result.state or "PENDING"

    resp = {'task_id': task_id, 'state': state}

    if state == 'SUCCESS':
        result = async_result.result or {}
        filename = None
        if isinstance(result, dict):
            filename = result.get('filename') or result.get('file')
        if filename:
            resp['download_url'] = f"/export/download/{filename}"
            resp['filename'] = filename
        else:
            resp['message'] = 'task completed but no filename returned'
    elif state in ('FAILURE', 'REVOKED'):
        try:
            resp['error'] = str(async_result.result)
        except Exception:
            resp['error'] = 'task failed'
    else:
        meta = async_result.info if hasattr(async_result, 'info') else None
        if meta:
            resp['meta'] = meta

    return jsonify(resp)

@export_bp.route('/list', methods=['GET'])
@token_required
def export_list():
    """
    List exported files for the currently authenticated user.
    Resolves EXPORT_DIR relative to project root if necessary.
    """
    import os
    from datetime import datetime

    current = getattr(request, 'current_user', None)
    if not current:
        return jsonify({'error': 'unauthenticated'}), 401

    # Project root (two levels up from this file, same as tasks.py)
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    # Read EXPORT_DIR from env (fallback to "exports" under project root)
    export_dir = os.environ.get('EXPORT_DIR', os.path.join(PROJECT_ROOT, "exports"))
    if not os.path.isabs(export_dir):
        export_dir = os.path.abspath(os.path.join(PROJECT_ROOT, export_dir))

    # Debug log - helps to confirm where Flask is looking
    current_app.logger.info("[EXPORT] listing directory=%s", export_dir)

    # If directory missing, return empty list (no error)
    if not os.path.exists(export_dir):
        return jsonify({'files': []})

    prefix = f"user_{current.id}_"
    files = []
    try:
        for fname in sorted(os.listdir(export_dir), reverse=True):
            if not fname.startswith(prefix):
                continue
            full = os.path.join(export_dir, fname)
            if not os.path.isfile(full):
                continue
            stat = os.stat(full)
            files.append({
                'filename': fname,
                'size_bytes': stat.st_size,
                'created_at': datetime.utcfromtimestamp(stat.st_mtime).isoformat() + 'Z',
                'download_url': f"/export/download/{fname}"
            })
    except Exception as e:
        current_app.logger.exception("Failed to list exports: %s", e)
        return jsonify({'error': 'failed_to_list', 'message': str(e)}), 500

    return jsonify({'files': files})


@export_bp.route('/download/<path:filename>', methods=['GET'])
@token_required
def export_download(filename):
    """
    Serve the exported CSV/PDF/HTML file as an attachment.

    - Normalizes EXPORT_DIR in the same way as the tasks module.
    - Protects against parent traversal in filename.
    """
    import os

    # disallow parent traversal or absolute filenames passed in the URL
    if ".." in filename or filename.startswith("/") or filename.startswith("\\"):
        return jsonify({'error': 'invalid filename'}), 400

    # Compute same project-root-based EXPORT_DIR as tasks.py
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    export_dir = os.environ.get('EXPORT_DIR', os.path.join(PROJECT_ROOT, "exports"))
    if not os.path.isabs(export_dir):
        export_dir = os.path.abspath(os.path.join(PROJECT_ROOT, export_dir))

    # Debug logging for troubleshooting
    current_app.logger.info("[EXPORT] download requested filename=%s, resolved_export_dir=%s", filename, export_dir)

    full_path = os.path.join(export_dir, filename)

    # Ensure file exists
    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        current_app.logger.error("[EXPORT] file not found: %s", full_path)
        return jsonify({'error': 'file_not_found', 'path_checked': full_path}), 404

    # send file
    try:
        # send_from_directory expects directory and filename
        return send_from_directory(export_dir, filename, as_attachment=True)
    except Exception as e:
        current_app.logger.exception("[EXPORT] failed to send file %s: %s", full_path, e)
        return jsonify({'error': 'download_failed', 'message': str(e)}), 500
