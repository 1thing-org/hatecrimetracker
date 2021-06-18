#!/bin/sh

python3 -m venv env
source env/bin/activate
pip install  -r requirements.txt
export DB_HOST=35.222.211.20:5432 
# 34.121.242.194:5432
export DB_USER=postgres
export DB_PASS=postgres
export DB_NAME=hatecrimetracker
python main.py