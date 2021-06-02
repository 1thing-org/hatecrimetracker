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

from load_data import traverse_file
from time import time
from incidents import getIncidents
from stats import getStats
from logging import error
from common import Incident
import datetime
import json

from flask import Flask, render_template, request

# [END gae_python3_datastore_store_and_fetch_user_times]
# [END gae_python38_datastore_store_and_fetch_user_times]
app = Flask(__name__)


def _getCommonArgs():
    start = request.args.get("start", DEFAULT_START_DATETIME)
    end = request.args.get("end", datetime.datetime.now())
    state = request.args.get("state", "")
    return start, end, state

@app.route('/')
def root():
    start, end, state = _getCommonArgs()
    incidents = getIncidents(start, end, state)
    return render_template(
        'index.html',
        incidents=incidents)

@app.route('/incidents')
def get_incidents():
    start, end, state = _getCommonArgs()
    incidents = getIncidents(start, end, state)
    return {"incidents":incidents};

DEFAULT_START_DATETIME = datetime.datetime.fromtimestamp(0)

@app.route('/stats')
def get_stats():
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

@app.route('/loaddata')
def load_data():  
    #loadData("data.json")
    traverse_file("data.json")
    return "success"
    
if __name__ == '__main__':
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.

    # Flask's development server will automatically serve static files in
    # the "static" directory. See:
    # http://flask.pocoo.org/docs/1.0/quickstart/#static-files. Once deployed,
    # App Engine itself will serve those files as configured in app.yaml.
    app.run(host='127.0.0.1', port=8081, debug=True)
