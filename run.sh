#!/bin/sh

python3 -m venv env
source env/bin/activate
# pip install  -r requirements.txt
# export DB_HOST=localhost:5432
export CLOUD_SQL_CONNECTION_NAME=crimetracker
export DB_USER=postgres
export DB_PASS=postgres
export DB_NAME=hatecrimetracker
python main.py