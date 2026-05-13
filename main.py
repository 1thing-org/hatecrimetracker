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
from firestore.incidents import deleteIncident, getIncidents, getStats, get_incident_by_id, update_user_report_contact
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
    # Default page_size matches what the web admin already sends explicitly.
    # The previous default of "10" silently truncated reads from clients that
    # don't send page_size (notably the old main-branch mobile app), making
    # `/incidents` look broken for them. The actual returned count is still
    # bounded by the date range and filters, so this isn't an unbounded read.
    page_size = request.args.get("page_size", "100000")
    return dateparser.parse(start), dateparser.parse(end), state, type, self_report_status, start_row, page_size


@app.route("/")
def root():
    start, end, state, type, self_report_status, start_row, page_size = _getCommonArgs()
    incidents = getIncidents(start, end, state, type, self_report_status, start_row, page_size)
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
    start, end, state, type, self_report_status, cursor, page_size = _getCommonArgs()
    
    # Get direction from query params (default to forward)
    direction = request.args.get("direction", "forward")
    
    # Handle cursor from different sources
    cursor = request.args.get("cursor") or request.args.get("next_cursor") or request.args.get("prev_cursor")
    
    skip_cache = request.args.get("skip_cache", "false")
    
    try:
        page_size = int(page_size) if str(page_size).isdigit() and int(page_size) > 0 else 10
    except ValueError:
        page_size = 10
    
    # Only check admin for self-report type when status is not approved
    if skip_cache.lower() == "true" or (type == "self-report" and self_report_status != "approved"):
        _check_is_admin(request)
    
    # Get incidents with pagination info
    result = getIncidents(start, end, state, type, self_report_status, cursor, direction, page_size, skip_cache.lower() == "true")
    
    # Check if it's an error response
    if isinstance(result, dict) and "error" in result:
        return jsonify(result), 400
    
    # Handle the response
    incidents = result.get("incidents", [])
    pagination = result.get("pagination", {})
    
    # Handle potential Sentinel type in the created_on field
    for incident in incidents:
        if isinstance(incident, dict) and 'created_on' in incident and incident['created_on'] == SERVER_TIMESTAMP:
            incident['created_on'] = None
    
    lang = _get_lang(request)
    
    # Translate incidents
    translated_incidents = translate_incidents(incidents, lang)
    clean_translated = clean_unused_translation(translated_incidents, lang)
    
    return {
        "incidents": clean_translated,
        "pagination": pagination,
    }


@app.route("/incidents/<id>", methods=["DELETE"])
def delete_incident(id):
    _check_is_admin(request)
    deleteIncident(id)
    return {"status": "success"}


@app.route("/incidents", methods=["POST"])
def upsert_incident():
    try:
        incident_data = request.get_json()
        if not incident_data:
            return jsonify({"error": "Invalid JSON payload."}), 400

        incident_type = incident_data.get("type")
        if incident_type not in ['news', 'self_report']:
            return jsonify({"error": "Incident 'type' must be 'news' or 'self_report'."}), 400

        # Admins are required to create 'news' incidents or update any existing incident
        if incident_type == 'news' or incident_data.get("id"):
            _check_is_admin(request)

        incident_id = firestore.incidents.upsert_incident(incident_data=incident_data)
        return jsonify({
            "message": "Incident reported successfully.",
            "incident_id": str(incident_id)
        }), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        print(f"Error in upsert_incident: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500

@app.route("/incidents/<id>/contact", methods=["POST"])
def update_incident_contact(id):
    """
    Updates contact information for a self-reported incident.
    """
    try:
        contact_data = request.get_json()
        if not contact_data:
            return jsonify({"error": "Invalid JSON payload."}), 400

        updated_id = update_user_report_contact(id, contact_data)
        
        return jsonify({
            "message": "Contact information updated successfully.",
            "incident_id": updated_id
        }), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404 # Not found or bad request
    except Exception as e:
        print(f"Error in update_incident_contact: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500

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
    # stats: [{"key": date, "value": count, "news": count, "self_report": count}] this is daily count filtered by state if needed
    # total: { "location": count } : total per state, not filtered by state
    # insight: { "location": {"news": count, "self_report": count} } : breakdown by type
    start_date, end_date, state, type, self_report_status, _, _ = _getCommonArgs()
    # If the caller didn't supply a `start`, _getCommonArgs falls back to the
    # project-wide default of 2019-11-01, which forces /stats to aggregate
    # ~7 years of incidents on every cold call. For /stats specifically that
    # is almost never what a viewer wants, so default to "one year before
    # end_date" by simply decrementing the year. /incidents and other
    # endpoints keep the wider default since callers (admin tools,
    # exporters) rely on it.
    if "start" not in request.args:
        try:
            start_date = end_date.replace(year=end_date.year - 1)
        except ValueError:
            # end_date is Feb 29 on a leap year — the previous year has no
            # Feb 29, so step back to Feb 28.
            start_date = end_date.replace(year=end_date.year - 1, day=28)
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

    # Convert aggregated to the format expected by production - just key and value for backward compatibility
    stats = [{"key": k, "value": v["news"] + v["self_report"]} for k, v in sorted(aggregated.items(), reverse=True)]

    # Create monthly breakdown (detailed objects) and monthly stats (simple numbers for backward compatibility)
    monthly_breakdown = monthly_stats  # Keep the detailed object structure
    monthly_stats = {k: v["news"] + v["self_report"] for k, v in monthly_breakdown.items()}  # Convert to simple numbers

    # NEW EXTENSIBLE FIELDS - {Key : structure}
    # daily_statistics: key = date (e.g. "2023-01-17")
    daily_statistics = {}
    for date_key, counts in aggregated.items():
        daily_statistics[date_key] = {
            "news": counts["news"], 
            "self_report": counts["self_report"]
        }
    
    # monthly_statistics: key = month (e.g. "2022-05") 
    monthly_statistics = {}
    for month, breakdown in monthly_breakdown.items():
        monthly_statistics[month] = {
            "news": breakdown["news"],
            "self_report": breakdown["self_report"]
        }
    
    # insights: key = location (e.g. "CA")
    insights = {}
    for location, breakdown in insight.items():
        insights[location] = {
            "news": breakdown["news"],
            "self_report": breakdown["self_report"]
        }

    return {
        # EXISTING FIELDS - Keep for production backward compatibility
        "stats": stats, 
        "total": total, 
        "monthly_stats": monthly_stats,
        
        # NEW EXTENSIBLE FIELDS - For new self-report feature
        "daily_statistics": daily_statistics,
        "monthly_statistics": monthly_statistics,
        "insights": insights
    }


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
