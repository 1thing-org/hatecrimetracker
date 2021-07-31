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

import datetime

from logging import error
from time import time
import firestore.admins
from flask import Flask, render_template, request
from flask_cors import CORS

from common import User
from firestore.incidents import getIncidents, getStats
from load_data import load_from_csv, traverse_file
from google.auth.transport import Response, requests
import google.oauth2.id_token
import firestore.cachemanager

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


def _get_user(request) -> User:
    id_token = request.cookies.get("token")
    if not id_token:
        [bearer, id_token] = request.headers.get("Authorization").split(" ")
        if bearer != "Bearer":
            raise ValueError("Bearer token expected")
    if id_token:
        try:
            claims = google.oauth2.id_token.verify_firebase_token(
                id_token, firebase_request_adapter)
            return User.from_dict(claims)
        except ValueError as exc:
            pass
    return None


def _getCommonArgs():
    start = request.args.get("start", (datetime.datetime.now(
    ) - datetime.timedelta(days=90)).strftime("%Y-%m-%d"))
    end = request.args.get("end", datetime.datetime.now().strftime("%Y-%m-%d"))
    state = request.args.get("state", "")
    return start, end, state


@app.route('/')
def root():
    start, end, state = _getCommonArgs()
    incidents = getIncidents(start, end, state)
    return render_template(
        'index.html',
        incidents=incidents,
        current_user=_get_user(request))


@app.route('/admin')
def admin():
    return render_template('admin.html')


@app.route('/isadmin')
def get_is_admin():
    return {"is_admin": _check_is_admin(request)}


@app.route('/incidents')
def get_incidents():
    start, end, state = _getCommonArgs()
    incidents = getIncidents(start, end, state)
    return {"incidents": incidents}


@app.route('/incidents/<incident_id>', methods=["DELETE"])
def delete_incident(incident_id):
    _check_is_admin(request)
    firestore.cachemanager.delete_incident(incident_id)
    return {"status": "success"}


@app.route('/incidents', methods=["POST"])
def create_incident(incident_id):
    _check_is_admin(request)
    req = request.get_json().get("incident")
    if req is None:
        raise ValueError("Missing incident")
    id = firestore.incidents.create_incident(req)
    return {"incident_id": id}


@app.route('/stats')
def get_stats():
    # return
    # stats: [{"key": date, "value": count}] this is daily count
    # total: { "location": count } : total per state
    start, end, state = _getCommonArgs()
    stats = getStats(start, end, state)
    total = {}
    if state:
        total[state] = 0
        for stat in stats:
            total[state] += stat["value"]
    else:
        # national data is by state and by date, merge all state per date, and calculate state total
        aggregated = {}
        for stat in stats:
            date = stat["key"]
            value = stat["value"]
            location = stat["incident_location"]
            aggregated[date] = aggregated.get(date, 0) + value
            total[location] = total.get(location, 0) + value
        stats = [{"key": k, "value": v} for k, v in aggregated.items()]

    return {"stats": stats, "total": total}

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


if __name__ == '__main__':
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.

    # Flask's development server will automatically serve static files in
    # the "static" directory. See:
    # http://flask.pocoo.org/docs/1.0/quickstart/#static-files. Once deployed,
    # App Engine itself will serve those files as configured in app.yaml.
    app.run(host='127.0.0.1', port=8081, debug=True)
