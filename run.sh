#!/bin/sh

python3.9 -m venv env
source env/bin/activate
pip install --upgrade pip
pip install  -r requirements.txt
export DB_HOST=34.121.242.194:5432
export DB_USER=postgres
export DB_PASS=postgres
export DB_NAME=hatecrimetracker
export GOOGLE_APPLICATION_CREDENTIALS=./hate-crime-tracker-7d52738f7212.json
python main.py