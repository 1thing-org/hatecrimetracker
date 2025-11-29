
"""Script to export Firestore collection as CSV."""

import csv
import sys
from pathlib import Path

from firebase_admin import credentials, firestore, initialize_app

CRED_FILE = Path(__file__).resolve().parent / 'hate-crime-tracker-7d52738f7212.json'
COLLECTION_NAME = 'incident'
FIELDS = ['title', 'incident_location', 'incident_time', 'incident_source', 'abstract', 'donation_link', 'help_the_victims', 'police_tip_line', 'publish_status', 'abstract_translate', 'created_by', 'created_on', 'help_the_victim', 'url', 'title_translate']
DIRECTION = firestore.Query.DESCENDING


def main():
    """Main function"""
    client = firebase_client(str(CRED_FILE))
    collection = client.collection(COLLECTION_NAME)

    writer = csv_writer(sys.stdout, FIELDS)
    writer.writeheader()
    for snapshot in collection.order_by('incident_time', direction=DIRECTION).get():
        data = snapshot.to_dict()
        writer.writerow(data)


def firebase_client(cred_file):
    """Generate Firebase client"""
    cred = credentials.Certificate(cred_file)
    app = initialize_app(credential=cred)
    client = firestore.client(app=app)
    return client


def csv_writer(file, fields):
    """Generate CSV writer"""
    return csv.DictWriter(file, fields)


if __name__ == '__main__':
    main()