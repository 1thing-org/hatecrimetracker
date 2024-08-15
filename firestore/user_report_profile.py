from datetime import datetime

import dateparser
from cachetools import cached
from fireo import models as mdl
import uuid
from google.cloud import firestore

from firestore.cachemanager import INCIDENT_CACHE, INCIDENT_STATS_CACHE, flush_cache

from enum import Enum

'''
class Status(Enum):
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
'''

class UserReportProfile(mdl.Model):
    report_ids = mdl.ListField(required=True)
    contact_name = mdl.TextField(required=True)
    email = mdl.TextField(required=True)
    phone = mdl.TextField(required=True)
    # status = Status(default=Status.UNDER_REVIEW)
    # created_on = mdl.DateTime(auto=True)


def update_user_profile(contact_name, email, phone, report_id='abc123'):
    # Initialize Firestore client
    db = firestore.Client()

    def get_user_report_by_report_id(report_id):
        # Reference to the userReport collection
        user_report_ref = db.collection('user_report')
        
        # Query for the document with the specified report_id
        query = user_report_ref.where('report_id', '==', report_id).stream()
        
        # Iterate over the query results and return the first match
        for doc in query:
            print(f"Document found: {doc.id}, Data: {doc.to_dict()}")
            return doc.id, doc.to_dict()  # Return both the document ID and its data
        
        # If no match found, return None
        print("No matching document found.")
        return None, None
    
    # Get the document ID and the user report data
    doc_id, user_report = get_user_report_by_report_id(report_id)
    
    if doc_id is None:
        return {"error": "Report ID not found"}, 404  # Return an error if the report_id does not exist

    # Reference to the specific document to update
    user_report_ref = db.collection('user_report').document(doc_id)
    
    # Update the document with the new details
    user_report_ref.update({
        'contact_name': contact_name,
        'email': email,
        'phone': phone
    })
    
    # Return the report_id in the response
    return {'report_id': report_id}, 200
