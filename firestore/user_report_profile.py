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


def update_user_profile(report_id, contact_name, email, phone):
     # Initialize Firestore client
    db = firestore.Client()

    def get_user_report_by_report_id(report_id):
        # Reference to the userReport collection
        user_report_ref = db.collection('userReport')
        
        # Query for the document with the specified report_id
        query = user_report_ref.where('report_id', '==', report_id).stream()
        
        # Iterate over the query results and return the first match
        for doc in query:
            return doc.to_dict()
        
        # If no match found, return None
        return None
    
    user_report_ref = get_user_report_by_report_id(report_id)
    # Create a user report object
    user_report_ref.update({
            'contact_name': contact_name,
            'email': email,
            'phone': phone,
            # 'created_on': datetime.now()
        })
    
    # Return the report_id in the response
    return {'report_id': report_id}

