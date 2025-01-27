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
from firestore.incidents import deleteIncident, getIncidents, getStats, insertIncident, getUserReports, insertUserReport, updateUserReport
from firestore.tokens import add_token
import incident_publisher


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
        "start", (date.fromisoformat("2022-11-01")).strftime("%Y-%m-%d")
    )
    end = request.args.get("end", datetime.now().strftime("%Y-%m-%d"))
    state = request.args.get("state", "")
    return dateparser.parse(start), dateparser.parse(end), state


@app.route("/")
def root():
    start, end, state = _getCommonArgs()
    incidents = getIncidents(start, end, state)
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
    start, end, state = _getCommonArgs()
    skip_cache = request.args.get("skip_cache", "false")
    if skip_cache.lower() == "true":
        _check_is_admin(request)  # only admin can set this flag to true
    incidents = getIncidents(start, end, state, skip_cache.lower() == "true")
    lang = _get_lang(request)
    return {
        "incidents": clean_unused_translation(
            translate_incidents(incidents, lang), lang
        )
    }


@app.route("/user_reports")
def get_user_reports():
    start, end, state = _getCommonArgs()
    skip_cache = request.args.get("skip_cache", "false")
    if skip_cache.lower() == "true":
        _check_is_admin(request)  # only admin can set this flag to true
    user_reports = getUserReports(start, end, state, skip_cache.lower() == "true")
    lang = _get_lang(request)
    return {
        "user_reports": clean_unused_translation(
            translate_incidents(user_reports, lang), lang
        )
    }


@app.route("/incidents/<incident_id>", methods=["DELETE"])
def delete_incident(incident_id):
    _check_is_admin(request)
    deleteIncident(incident_id)
    return {"status": "success"}


@app.route("/incidents", methods=["POST"])
def create_incident():
    try:
        # _check_is_admin(request)
        req = request.get_json().get("incident")
        if req is None:
            return jsonify({"error": "Invalid request data or internal server error."}), 400
        id = insertIncident(req)
        return jsonify({
            "message": "Incident reported successfully.",
            "user_report_id": str(id)
        }), 201
    except Exception as e:
        # log the exception e if needed
        return jsonify({"error": "Invalid request data or internal server error."}), 500


def _aggregate_monthly_total(fullmonth_stats, state):
    monthly_total = {}
    for daily in fullmonth_stats:
        location = daily["incident_location"]
        if not state or state == location:
            str_month = datetime.strptime(daily["key"], "%Y-%m-%d").strftime("%Y-%m")
            monthly_total[str_month] = monthly_total.get(str_month, 0) + daily["value"]
    return monthly_total


@app.route("/stats")
def get_stats():
    # return
    # stats: [{"key": date, "value": count}] this is daily count filtered by state if needed
    # total: { "location": count } : total per state, not filtered by state
    start_date, end_date, state = _getCommonArgs()
    str_start = start_date.strftime("%Y-%m-%d")
    str_end = end_date.strftime("%Y-%m-%d")

    fullmonth_stats = getStats(
        start_date.replace(day=1),
        end_date.replace(day=calendar.monthrange(end_date.year, end_date.month)[1]),
    )  # [{key(date), incident_location, value}]
    monthly_stats = _aggregate_monthly_total(fullmonth_stats, state)
    total = {}
    # national data is by state and by date, merge all state per date, and calculate state total
    aggregated = {}
    for stat in fullmonth_stats:
        str_date = stat["key"]
        if str_date < str_start or str_date > str_end:
            continue

        value = stat["value"]
        location = stat["incident_location"]
        # national total count will always include all states
        total[location] = total.get(location, 0) + value
        if not state or state == location:
            # if state is specified, only aggregate state daily data
            # otherwise aggregate all data
            aggregated[str_date] = aggregated.get(str_date, 0) + value

    stats = [{"key": k, "value": v} for k, v in aggregated.items()]

    return {"stats": stats, "total": total, "monthly_stats": monthly_stats}


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
    if req is None:
        raise ValueError("Missing user report")
    id = insertUserReport(req)
    return {"user_report_id": id}

@app.route("/user_report_profile", methods=["POST"])
def update_user_report():
    data = request.get_json(force=True).get("user_report")
    if not (response['report_id']):
        raise ValueError("Missing user report")
        # return {"error": "Missing data"}, 400
    if data.get('status'):
        _check_is_admin(request)
    response, code = updateUserReport(data)
    return {"report_id": response['report_id']}, code


if __name__ == "__main__":
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.

    # Flask's development server will automatically serve static files in
    # the "static" directory. See:
    # http://flask.pocoo.org/docs/1.0/quickstart/#static-files. Once deployed,
    # App Engine itself will serve those files as configured in app.yaml.

    app.run(host="0.0.0.0", port=8081, debug=True)
    # run on 0.0.0.0 for easy access for the development
