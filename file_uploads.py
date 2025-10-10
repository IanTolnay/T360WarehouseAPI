"""
file_upload.py – T360 Google Drive Upload Endpoint
Handles direct binary uploads (multipart/form-data)
and routes them automatically to the correct Drive folder.
"""

import os
import logging

from flask import Blueprint, request, jsonify
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account

# ---------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------
logger = logging.getLogger("t360-api")

# ---------------------------------------------------------------------
# Blueprint Initialization
# ---------------------------------------------------------------------
upload_bp = Blueprint("upload_bp", __name__)

# ---------------------------------------------------------------------
# Google Drive Configuration
# ---------------------------------------------------------------------
SERVICE_ACCOUNT_FILE = "/etc/secrets/creds.json"  # Path to your service account key
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
drive_service = build("drive", "v3", credentials=creds)

# ---------------------------------------------------------------------
# Folder Auto-Routing Map
# ---------------------------------------------------------------------
FOLDER_MAP = {
    "sales order": "1lA9LqQFDTALlMNAtiUGeJjb82TV4_MxS",
    "purchase order": "1FMz09LHGNEUS-VjNKlSzIHvVs8lWyKEC",
    "ticket": "1e_-Rujp6wcOXH3AptJF4lEWEpoOabxpa",
    "return": "1lNMjcM81iY-l41QYVVTCpO8c9oY998Mx",
    "damage": "13z5Odm48_EoHnINYc5_lvtpLSyUEYPRw",
    "booking": "1Q7SPz-x3NzdpjVWR6pENTUm4cNu8zSml",
    "misc": "13sny-GOGWw5od74oWu6xlc6duQ9crZtb",
}

DEFAULT_FOLDER_ID = "15OAwN8yyMhUJFCeGK11_h7mptvSYWukN"


def detect_folder(filename: str) -> str:
    """Try to auto-detect Drive folder from filename keywords."""
    name = filename.lower()
    for key, folder_id in FOLDER_MAP.items():
        if key in name:
            return folder_id
    return DEFAULT_FOLDER_ID


# ---------------------------------------------------------------------
# Upload Route
# ---------------------------------------------------------------------
@upload_bp.route("/upload/file", methods=["POST"])
def upload_file():
    try:
        uploaded_file = request.files.get("file")

        # --- Fallback for when Action sends base64 JSON instead of multipart file ---
        if not uploaded_file and request.is_json:
            data = request.get_json(silent=True)
            base64_data = data.get("file") or data.get("base64_data")
            filename = data.get("filename", "uploaded_from_gpt.png")
            if base64_data:
                from io import BytesIO
                import base64
                file_bytes = base64.b64decode(base64_data)
                uploaded_file = BytesIO(file_bytes)
                uploaded_file.filename = filename
        if not uploaded_file:
            return jsonify({"error": "No file provided"}), 400

        folder_id = request.form.get("folder_id") or detect_folder(uploaded_file.filename)
        temp_path = os.path.join("/tmp", uploaded_file.filename)
        uploaded_file.save(temp_path)

        media = MediaFileUpload(temp_path, mimetype=uploaded_file.mimetype, resumable=True)
        metadata = {"name": uploaded_file.filename, "parents": [folder_id]}

        uploaded = drive_service.files().create(
            body=metadata, media_body=media, fields="id, name, parents, webViewLink"
        ).execute()

        os.remove(temp_path)

        # Log detailed response for Render logs
        logger.info(f"Drive upload response: {uploaded}")

        return jsonify({
            "status": "success",
            "file_id": uploaded.get("id"),
            "url": uploaded.get("webViewLink"),
            "folder_used": folder_id,
            "drive_response": uploaded
        }), 200

    except Exception as e:
        import traceback
        err_trace = traceback.format_exc()
        logger.error(f"Drive upload failed: {e}\n{err_trace}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "traceback": err_trace
        }), 500


@upload_bp.route("/health/drive", methods=["GET"])
def drive_health_check():
    """
    Runs a quick health check to verify Drive API connectivity and folder access.
    """
    import traceback
    try:
        folder_id = request.args.get("folder_id") or "15OAwN8yyMhUJFCeGK11_h7mptvSYWukN"
        # Query a few files from the folder to confirm access
        results = (
            drive_service.files()
            .list(q=f"'{folder_id}' in parents", pageSize=5, fields="files(id, name)")
            .execute()
        )
        files = results.get("files", [])
        return jsonify({
            "status": "ok",
            "folder_checked": folder_id,
            "files_found": files
        }), 200
    except Exception as e:
        err_trace = traceback.format_exc()
        return jsonify({
            "status": "error",
            "message": str(e),
            "traceback": err_trace
        }), 500

