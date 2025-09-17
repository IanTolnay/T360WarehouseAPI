from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import gspread
import os
import json
import logging
from functools import wraps

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.DEBUG)

@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "Worker API online"}), 200

# Load Google credentials
with open("creds.json", "r") as f:
    creds_dict = json.load(f)

gc = gspread.service_account_from_dict(creds_dict)
spreadsheet = gc.open_by_key(os.environ.get("SPREADSHEET_ID"))

# Authorization
WRITE_KEY = os.environ.get("INVENTORY_WRITE_KEY")
def require_write_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        key = request.args.get("key") or request.headers.get("Authorization", "").replace("Bearer ", "")
        if key != WRITE_KEY:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.before_request
def log_all_requests():
    try:
        method = request.method
        path = request.path
        headers = dict(request.headers)
        json_payload = request.get_json(silent=True)
        logging.warning(f"🛰️ {method} {path} | Headers: {headers} | Body: {json_payload}")
    except Exception as e:
        logging.error(f"❌ Request logging failed: {str(e)}")

@app.route("/sheet/write_row", methods=["POST"])
@require_write_key
def write_row():
    try:
        data = request.get_json(force=True)
        sheet_name = data.get("sheet_name")
        item = data.get("item", {})

        worksheet = spreadsheet.worksheet(sheet_name)
        headers = worksheet.row_values(1)
        new_keys = [key for key in item.keys() if key not in headers]
        if new_keys:
            headers += new_keys
            worksheet.delete_rows(1)
            worksheet.insert_row(headers, 1)

        row = [item.get(header, "") for header in headers]
        worksheet.append_row(row)

        return jsonify({"message": "Row written", "row": row}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/sheet/write_passthrough", methods=["POST"])
@require_write_key
def write_passthrough():
    try:
        data = request.get_json(force=True)
        sheet_name = data.get("sheet_name")
        if not sheet_name:
            return jsonify({"error": "Missing sheet_name"}), 400

        item = {k: v for k, v in data.items() if k != "sheet_name"}

        worksheet = spreadsheet.worksheet(sheet_name)
        headers = worksheet.row_values(1)
        new_keys = [key for key in item.keys() if key not in headers]
        if new_keys:
            headers += new_keys
            worksheet.delete_rows(1)
            worksheet.insert_row(headers, 1)

        row = [item.get(header, "") for header in headers]
        worksheet.append_row(row)

        return jsonify({"message": "Row written", "row": row}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/sheet/write_passthrough_log", methods=["POST"])
@require_write_key
def write_passthrough_log():
    try:
        data = request.get_json(force=True)
        log_sheet = spreadsheet.worksheet("3.3_Test_Sandbox")
        headers = log_sheet.row_values(1)
        new_keys = [key for key in data.keys() if key not in headers]

        if new_keys:
            headers += new_keys
            log_sheet.delete_rows(1)
            log_sheet.insert_row(headers, 1)

        row = [data.get(header, "") for header in headers]
        log_sheet.append_row(row)

        return jsonify({"message": "Logged payload successfully", "data": data}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/updateSheetHeaders", methods=["POST"])
@require_write_key
def update_headers():
    data = request.json
    sheet_name = data.get("sheet_name")
    headers = data.get("headers")
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
        worksheet.clear()
        worksheet.insert_row(headers, 1)
        return jsonify({"status": "headers updated"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
        
@app.route("/sheet/get_headers", methods=["POST"])
@require_write_key
def get_sheet_headers():
    data = request.get_json(force=True)
    sheet_name = data.get("sheet_name")
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
        headers = worksheet.row_values(1)
        return jsonify({"headers": headers}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/sheet/get_all", methods=["POST"])
@require_write_key
def get_all_sheet_data():
    data = request.get_json(force=True)
    sheet_name = data.get("sheet_name")
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
        all_data = worksheet.get_all_values()
        return jsonify({"data": all_data}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/log", methods=["POST"])
@require_write_key
def log_event():
    data = request.json
    data["sheet_name"] = "4.5_Log_Index"
    return write_row()

@app.route("/integration/log", methods=["POST"])
@require_write_key
def log_integration():
    try:
        data = request.get_json()
        worksheet = spreadsheet.worksheet("1.2_Integration_Log")
        headers = worksheet.row_values(1)
        new_keys = [key for key in data.keys() if key not in headers]
        if new_keys:
            worksheet.insert_row(headers + new_keys, 1)
            headers += new_keys
        row = [data.get(header, "") for header in headers]
        worksheet.append_row(row)
        return jsonify({"message": "Integration log added successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/sheet/create", methods=["POST"])
@require_write_key
def create_sheet():
    data = request.get_json()
    name = data.get("sheet_name")
    headers = data.get("headers", [])
    try:
        spreadsheet.add_worksheet(title=name, rows="1000", cols="26")
        if headers:
            worksheet = spreadsheet.worksheet(name)
            worksheet.insert_row(headers, 1)
        return jsonify({"message": f"Sheet '{name}' created"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/sheet/set_headers", methods=["POST"])
@require_write_key
def set_headers():
    data = request.get_json()
    sheet_name = data.get("sheet_name")
    headers = data.get("headers")
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
        worksheet.clear()
        worksheet.insert_row(headers, 1)
        return jsonify({"message": "Headers updated successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/sheet/update_structure", methods=["POST"])
@require_write_key
def update_structure():
    data = request.get_json()
    sheet_name = data.get("sheet_name")
    remove_columns = data.get("remove_columns", [])
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
        all_data = worksheet.get_all_values()
        if not all_data:
            return jsonify({"error": "Sheet is empty"}), 400
        header = all_data[0]
        new_header = [h for h in header if h not in remove_columns]
        new_data = []
        for row in all_data[1:]:
            new_row = [val for i, val in enumerate(row) if header[i] not in remove_columns]
            new_data.append(new_row)
        worksheet.clear()
        worksheet.append_row(new_header)
        for row in new_data:
            worksheet.append_row(row)
        return jsonify({"message": "Structure updated"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/sheet/delete", methods=["POST"])
@require_write_key
def delete_sheet():
    data = request.get_json()
    sheet_name = data.get("sheet_name")
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
        spreadsheet.del_worksheet(worksheet)
        return jsonify({"message": f"Sheet '{sheet_name}' deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/sheet/list_all", methods=["GET"])
def list_all_sheets():
    try:
        sheet_titles = [ws.title for ws in spreadsheet.worksheets()]
        return jsonify({"sheets": sheet_titles})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/inventory/<sheet_name>", methods=["GET"])
def get_inventory(sheet_name):
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
        headers = worksheet.row_values(1)
        all_values = worksheet.get_all_values()
        rows = all_values[1:] if len(all_values) > 1 else []
        records = [
            {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}
            for row in rows
        ] if rows else []
        return jsonify(records if records else [{"headers_only": headers}]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/inventory/structured/<sheet_name>", methods=["GET"])
def get_structured(sheet_name):
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
        values = worksheet.get_all_values()
        headers = values[0] if values else []
        rows = values[1:] if len(values) > 1 else []
        return jsonify({"headers": headers, "rows": rows})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/inventory/raw/<sheet_name>", methods=["GET"])
def get_raw_sheet(sheet_name):
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
        max_rows = worksheet.row_count
        raw = worksheet.get(f"A1:Z{max_rows}")
        return jsonify(raw), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/inventory/item/<sheet_name>/<item_name>")
def get_item(sheet_name, item_name):
    try:
        key_column = request.args.get("key_column")
        worksheet = spreadsheet.worksheet(sheet_name)
        records = worksheet.get_all_records()
        if not records:
            return jsonify({"error": "No data in sheet."}), 404
        match = None
        if key_column:
            match = next((r for r in records if str(r.get(key_column, "")).lower() == item_name.lower()), None)
        else:
            match = next((r for r in records if item_name.lower() in [str(v).lower() for v in r.values()]), None)
        if match:
            return jsonify(match), 200
        return jsonify({"error": "Item not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/sheet/rename", methods=["POST"])
@require_write_key
def rename_sheet():
    data = request.get_json()
    old_name = data.get("old_name")
    new_name = data.get("new_name")
    try:
        worksheet = spreadsheet.worksheet(old_name)
        worksheet.update_title(new_name)
        return jsonify({"message": f"Renamed {old_name} to {new_name}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/openapi.yaml")
def openapi_spec():
    return send_file("openapi.yaml", mimetype="text/yaml")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=True)
