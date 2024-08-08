from datetime import datetime

import dateparser
from cachetools import cached
from fireo import models as mdl
import uuid
from google.cloud import firestore

from firestore.cachemanager import INCIDENT_CACHE, INCIDENT_STATS_CACHE, flush_cache

from enum import Enum

class Status(Enum):
    UNDER_REVIEW = 1
    APPROVED = 2
    REJECTED = 3

class UserProfile(mdl.Model):
    report_ids = mdl.ListField(required=True)
    contact_name = mdl.TextField(required=True)
    email = mdl.TextField(required=True)
    phone = mdl.TextField(required=True)
    status = Status(default=1)
    created_on = mdl.DateTime(auto=True)

def add_user_report(report_id, contact_name, email, phone):
    # Generate a unique report_id
    report_id = str(uuid.uuid4())
    
    # Create a user report object
    user_report = UserProfile(
        report_ids=mdl.MapField(default={}),
        contact_name=contact_name,
        email=email,
        phone=phone,
        status=Status.UNDER_REVIEW,
        created_on=datetime.now()
    )
    
    # Initialize Firestore client
    db = firestore.Client()
    
    # Fetch the user's profile document reference
    user_doc_ref = db.collection('user_profiles').document(email)
    user_doc = user_doc_ref.get()
    
    if user_doc.exists:
        # User exists, update the report_ids list
        user_data = user_doc.to_dict()
        report_ids = user_data.get('report_ids', [])
        report_ids.append(report_id)
        user_doc_ref.update({'report_ids': report_ids})
    else:
        # User does not exist, create a new user profile
        user_profile = UserProfile(
            report_ids=[report_id],
            contact_name=contact_name,
            email=email,
            phone=phone,
            status=Status.UNDER_REVIEW,
            created_on=datetime.now()
        )
        user_doc_ref.set({
            'report_ids': user_profile.report_ids,
            'contact_name': user_profile.contact_name,
            'email': user_profile.email,
            'phone': user_profile.phone,
            'status': user_profile.status.name,  # Save the status name
            'created_on': user_profile.created_on
        })
    
    # Return the report_id in the response
    return {'report_id': report_id}

