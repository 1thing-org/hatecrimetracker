#!/bin/sh
python3.9 -m venv env
source env/bin/activate
pip install --upgrade pip
pip install  -r requirements.txt
export GOOGLE_APPLICATION_CREDENTIALS=./hate-crime-tracker-7d52738f7212.json
python main.py