# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import calendar
from datetime import datetime, timedelta, date
import dateparser
from logging import error
from time import time
from translate import translate_incidents, clean_unused_translation

import google.oauth2.id_token
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from google.auth.transport import Response, requests

import firestore.admins
from common import User
from firestore.incidents import deleteIncident, getIncidents, getStats, insertIncident, insertUserReport, updateUserReport, get_incident_by_id
from firestore.tokens import add_token
import incident_publisher
from google.cloud.firestore_v1 import SERVER_TIMESTAMP


# [END gae_python3_datastore_store_and_fetch_user_times]
# [END gae_python38_datastore_store_and_fetch_user_times]
app = Flask(__name__)
# cors = CORS(app, resources={r"/*": {"origins": "*"}})
cors = CORS(app)
firebase_request_adapter = requests.Request()


def _check_is_admin(request) -> bool:
    user = _get_user(request)
    if not user or not firestore.admins.is_admin(user.email):
        raise PermissionError("Lack of permission")
    return True


def _get_lang(request) -> str:
    lang = (
        request.args.get("lang")
        if request.args.get("lang")
        else request.cookies.get("lang")
    )
    if lang is None:
        lang = "en"
    return lang


def _get_user(request) -> User:
    id_token = request.cookies.get("token")
    if not id_token and request.headers.get("Authorization"):
        [bearer, id_token] = request.headers.get("Authorization").split(" ")
        if bearer != "Bearer":
            raise ValueError("Bearer token expected")
    if id_token:
        try:
            claims = google.oauth2.id_token.verify_firebase_token(
                id_token, firebase_request_adapter
            )
            return User.from_dict(claims)
        except ValueError as exc:
            print(exc)
            pass
    return None


def _getCommonArgs():
    start = request.args.get(
        "start", (date.fromisoformat("2019-11-01")).strftime("%Y-%m-%d")
    )
    end = request.args.get("end", datetime.now().strftime("%Y-%m-%d"))
    state = request.args.get("state", "")
    type = request.args.get("type", "")
    self_report_status = request.args.get("self_report_status", "")
    start_row = request.args.get("start_row", "")
    page_size = request.args.get("page_size", "")
    return dateparser.parse(start), dateparser.parse(end), state, type, self_report_status, start_row, page_size


@app.route("/")
def root():
    start, end, state, type, self_report_status, start_row, page_size = _getCommonArgs()
    incidents = getIncidents(start, end, state, type, self_report_status, start_row, page_size)
    print(incidents)
    return render_template(
        "index.html", incidents=incidents, current_user=_get_user(request)
    )


@app.route("/admin")
def admin():
    return render_template("admin.html")


@app.route("/isadmin")
def get_is_admin():
    return {"is_admin": _check_is_admin(request)}


@app.route("/incidents")
def get_incidents():
    start, end, state, type, self_report_status, start_row, page_size = _getCommonArgs()
    skip_cache = request.args.get("skip_cache", "false")
    
    # Only check admin for self-report type when status is not approved
    if skip_cache.lower() == "true" or (type == "self-report" and self_report_status != "approved"):
        _check_is_admin(request)
    # Get incidents (this might return an error response instead of a list)
    incidents = getIncidents(start, end, state, type, self_report_status, start_row, page_size, skip_cache.lower() == "true")
    
    # Check if incidents is an error response
    if isinstance(incidents, dict) and "error" in incidents:
        return jsonify(incidents), 400

    # Handle potential Sentinel type in the created_on field
    for incident in incidents:
        if isinstance(incident, dict) and 'created_on' in incident and incident['created_on'] == SERVER_TIMESTAMP:
            incident['created_on'] = None

    lang = _get_lang(request)

    # In the response, include the ID of the last document for pagination
    last_doc_id = None
    if incidents and len(incidents) > 0:
        last_doc_id = incidents[-1].get('id')  # Assuming 'id' is stored in the document
    
    translated_incidents = translate_incidents(incidents, lang)
    
    # Add safety check for string values
    cleaned_incidents = []
    string_items_found = False
    
    for item in translated_incidents:
        if isinstance(item, str):
            string_items_found = True
            print(f"Found string item: {item}")
            # You could skip it or convert it to a dict if appropriate
        else:
            cleaned_incidents.append(item)
    
    if string_items_found:
        # Log this unexpected condition
        print("Warning: String items found in translated incidents")
    
    return {
        "incidents": clean_unused_translation(
            translate_incidents(incidents, lang), lang
        )
        # , "last_doc_id": last_doc_id
    }


@app.route("/incidents/<id>", methods=["DELETE"])
def delete_incident(id):
    _check_is_admin(request)
    deleteIncident(id)
    return {"status": "success"}


@app.route("/incidents", methods=["POST"])
def create_incident():
    try:
        # _check_is_admin(request)
        req = request.get_json().get("incident")
        if req is None or not req.get("abstract") or not req.get("abstract_translate") or not req.get("incident_source"):
            return jsonify({"error": "Invalid request data or internal server error."}), 400
        id = insertIncident(req)
        return jsonify({
            "message": "Incident reported successfully.",
            "user_report_id": str(id)
        }), 201
    except Exception as e:
        # log the exception e if needed
        return jsonify({"error": "Invalid request data or internal server error."}), 500


def _aggregate_monthly_total(stats, state=None):
    monthly_total = {}
    for daily in stats:
        # Skip if state is specified and doesn't match
        if state and daily["incident_location"] != state:
            continue
        # Convert YYYY-MM-DD to YYYY-MM
        str_month = daily["key"][:7]
        # Store separate counts for news and self-report for frontend needs
        if str_month not in monthly_total:
            monthly_total[str_month] = {"news": 0, "self_report": 0}
        monthly_total[str_month]["news"] += daily["news"]
        monthly_total[str_month]["self_report"] += daily["self_report"]
    return monthly_total


@app.route("/stats")
def get_stats():
    # return
    # stats: [{"key": date, "news": count, "self_report": count}] this is daily count filtered by state if needed
    # total: { "location": count } : total per state, not filtered by state
    # insight: { "location": {"news": count, "self_report": count} } : breakdown by type
    start_date, end_date, state, type, self_report_status, _, _ = _getCommonArgs()
    str_start = start_date.strftime("%Y-%m-%d")
    str_end = end_date.strftime("%Y-%m-%d")

    # Use the type parameter from request instead of hardcoding "both"
    fullmonth_stats = getStats(
        start_date.replace(day=1),
        end_date.replace(day=calendar.monthrange(end_date.year, end_date.month)[1]),
        "",  # Empty state to get all states, this is by design
        type,  # Use the type filter from the request
        self_report_status  # Pass through any self_report_status filter
    )  # [{key(date), incident_location, news, self_report}]
    monthly_stats = _aggregate_monthly_total(fullmonth_stats, state)  # Pass state here for filtering
    
    # Initialize both total and insight dictionaries
    total = {}
    insight = {}  # New field for type breakdown
    
    # national data is by state and by date, merge all state per date, and calculate state total
    aggregated = {}
    for stat in fullmonth_stats:
        str_date = stat["key"]
        if str_date < str_start or str_date > str_end:
            continue

        # Sum news and self_report for total value
        value = stat["news"] + stat["self_report"]
        location = stat["incident_location"]
        
        # Always include in totals regardless of state filter
        total[location] = total.get(location, 0) + value
        
        # Initialize the insight object for this location if not exists
        if location not in insight:
            insight[location] = {"news": 0, "self_report": 0}
            
        # Count by type in insight - always include in totals regardless of state filter
        insight[location]["news"] += stat["news"] 
        insight[location]["self_report"] += stat["self_report"]
        
        # Only include in daily stats if matches state filter
        if not state or state == location:
            if str_date not in aggregated:
                aggregated[str_date] = {"news": 0, "self_report": 0}
            aggregated[str_date]["news"] += stat["news"]
            aggregated[str_date]["self_report"] += stat["self_report"]

    # Convert aggregated to the format expected by frontend
    stats = [{"key": k, "news": v["news"], "self_report": v["self_report"]} for k, v in aggregated.items()]

    return {"stats": stats, "total": total, "monthly_stats": monthly_stats, "insight": insight}


@app.route("/publish_incidents")
def publish_incidents():

    # header = request.headers.get("X-CloudScheduler", None)
    # if not header:
    #     raise ValueError(
    #         "attempt to access cloud scheduler handler directly, "
    #         "missing custom X-CloudScheduler header"
    #     )

    result = incident_publisher.publish_incidents()
    return {"success": True, "result": result}


# @app.route('/loaddata')
# def load_data():
#     #loadData("data.json")
#     traverse_file("data.json")
#     return "success"

# @app.route('/loadcsv')
# def load_csv():
#     #Load incidents from loaddata_result.csv
#     #loadData("data.json")
#     load_from_csv("loadtata_result.csv")
#     return "success"


@app.route("/token", methods=["PUT"])
def register_token():
    deviceId = request.get_json().get("deviceId", None)
    token = request.get_json().get("token", None)
    if not deviceId:
        raise ValueError("No deviceId detected")
    if not token:
        raise ValueError("No token detected")

    res = add_token(deviceId, token)
    return {"success": True}


@app.route("/user_reports", methods=["POST"])
def create_user_report():
    req = request.get_json().get("user_report")
    req["type"] = "user_report"  # Ensure the type is set to user_report
    
    if req is None or not req.get("abstract") or not req.get("incident_location")  or not req.get("incident_time"):
        raise ValueError("Missing user report abstract, location or time ")
    id = insertUserReport(req)
    return {"user_report_id": id}

@app.route("/user_report_profile", methods=["POST"])
def update_user_report():
    data = request.get_json(force=True).get("user_report")
    if not data or not data.get("report_id"):
        return {"error": "Missing report_id"}, 400

    if data.get('status'):  # Only admins can update the status
        _check_is_admin(request)

    # Call the updateUserReport function and get the response and status code
    response, code = updateUserReport(data)
    return response, code

# Admin-only endpoint to view user reported incident details that may including private contact information
@app.route('/incidents/<id>', methods=['GET'])
def get_incident(id):
    try:
        _check_is_admin(request)
        response, code = get_incident_by_id(id)
        return jsonify(response), code
    except Exception as e:
        print(f"Error in get_incident endpoint: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.

    # Flask's development server will automatically serve static files in
    # the "static" directory. See:
    # http://flask.pocoo.org/docs/1.0/quickstart/#static-files. Once deployed,
    # App Engine itself will serve those files as configured in app.yaml.

    app.run(host="0.0.0.0", port=8088, debug=True)
    # run on 0.0.0.0 for easy access for the development
