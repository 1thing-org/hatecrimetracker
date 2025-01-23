#!/bin/sh

# Run server code against local firebase simulator
python3.10 -m venv env
source env/bin/activate
pip install --upgrade pip
pip install  -r requirements.txt
export GOOGLE_APPLICATION_CREDENTIALS=./hate-crime-tracker-7d52738f7212.json
export FIRESTORE_EMULATOR_HOST="localhost:8080"
export STORAGE_EMULATOR_HOST="http://localhost:9199"
python3.10 main.py
