#!/bin/sh
python -m venv env
# source env/bin/activate
python -m pip install --upgrade pip
python -m pip install  -r requirements.txt
export GOOGLE_APPLICATION_CREDENTIALS=./hate-crime-tracker-7d52738f7212.json
python main.py