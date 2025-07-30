from flask import Flask, request, jsonify
from functools import wraps
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Load credentials and spreadsheet
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
gc = gspread.authorize(creds)
spreadsheet = gc.open_by_key(os.environ.get("SPREADSHEET_ID"))

app = Flask(__name__)

# Auth decorator
WRITE_KEY = os.environ.get("INVENTORY_WRITE_KEY")
def require_write_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.args.get("key") or request.headers.get("Authorization", "").replace("Bearer ", "")
        if key != WRITE_KEY:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

# Generic write_row endpoint
@app.route("/sheet/write_row", methods=["POST"])
@require_write_key
def write_row():
    data = request.json
    sheet_name = data.get("sheet_name")
    item = data.get("item")
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
        headers = worksheet.row_values(1)
        row = [item.get(header, "") for header in headers]
        worksheet.append_row(row)
        return jsonify({"status": "success", "row": row})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Header update endpoint
@app.route("/updateSheetHeaders", methods=["POST"])
@require_write_key
def update_headers():
    data = request.json
    sheet_name = data.get("sheet_name")
    headers = data.get("headers")
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
        worksheet.delete_rows(1)
        worksheet.insert_row(headers, 1)
        return jsonify({"status": "headers updated"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Log event endpoint
@app.route("/log", methods=["POST"])
@require_write_key
def log_event():
    data = request.json
    data["sheet_name"] = "4.5_Log_Index"
    return write_row()

# Run Flask
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)


