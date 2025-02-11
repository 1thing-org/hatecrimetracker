from datetime import datetime

import dateparser
from cachetools import cached
from fireo import models as mdl

from google.cloud import firestore
from firestore.cachemanager import INCIDENT_CACHE, INCIDENT_STATS_CACHE, flush_cache
from firestore.get_all_validation import get_all_validation


class BaseReport(mdl.Model):
    created_on = mdl.DateTime(auto=True)
    publish_status = mdl.MapField(
        required=True, default={"twitter": None, "linkedin": None, "notification": None}
    )
    donation_link = mdl.TextField()  # Link to donation website
    police_tip_line = mdl.TextField()  # Phone number to provide tips to police
    help_the_victim = mdl.TextField()  # Text about how people can help the victim
    class Meta:
        abstract = True  # Mark this model as abstract


class UserReport(BaseReport):
    user_report_time = mdl.DateTime(required=True)
    user_report_location = mdl.TextField(required=True)
    description = mdl.TextField(required=True)
    description_translate = mdl.MapField(required=False)
    attachments = mdl.TextField(required=True)
    status = mdl.TextField(required=False)
    approved_by = mdl.TextField(required=False)
    report_id = mdl.ListField(required=False)
    contact_name = mdl.TextField(required=False)
    email = mdl.TextField(required=False)
    phone = mdl.TextField(required=False)
    class Meta:
        collection_name = "incident"  # Force this class to use the "incident" collection


class Incident(BaseReport):
    incident_time = mdl.DateTime(required=True)
    incident_location = mdl.TextField()
    abstract = mdl.TextField(required=True)
    abstract_translate = mdl.MapField(required=True)
    url = mdl.TextField(required=False)
    incident_source = mdl.TextField(required=True)
    created_by = mdl.TextField(required=False)
    title = mdl.TextField(required=False)
    title_translate = mdl.MapField(required=False)
    parent_doc = mdl.TextField(column_name="parent")


@cached(cache=INCIDENT_CACHE)
def queryIncidents(start: datetime, end: datetime, state=""):
    end_time = datetime(end.year, end.month, end.day, 23, 59, 59)
    query = Incident.collection.filter("incident_time", ">=", start).filter(
        "incident_time", "<=", end_time
    )
    if state != "":
        query = query.filter("incident_location", "==", state)

    result = query.order("-incident_time").fetch()
    return [incident.to_dict() for incident in result]


def deleteIncident(incident_id):
    if Incident.collection.delete("incident/" + incident_id):
        flush_cache()
        return True
    return False


def getIncidents(start: datetime, end: datetime, state="", skip_cache=False):
    if skip_cache:
        INCIDENT_CACHE.clear()
    return queryIncidents(start, end, state)


def insertIncident(incident, to_flush_cache=True):
    # return incident id
    print("INSERTING:", incident)
    new_incident = Incident(
        incident_time=(
            dateparser.parse(incident["incident_time"])
            if isinstance(incident["incident_time"], str)
            else incident["incident_time"]
        ),
        incident_location=incident["incident_location"],
        abstract=incident["abstract"],
        url=incident["url"],
        incident_source=incident["incident_source"],
        created_by=incident["created_by"],
        title=incident["title"],
    )

    new_incident.id = incident["id"] if "id" in incident else None
    new_incident.abstract_translate = (
        incident["abstract_translate"] if "abstract_translate" in incident else {}
    )
    new_incident.title_translate = (
        incident["title_translate"] if "title_translate" in incident else {}
    )
    new_incident.publish_status = (
        incident["publish_status"] if "publish_status" in incident else {}
    )
    new_incident.donation_link = (
        incident["donation_link"] if "donation_link" in incident else None
    )
    new_incident.police_tip_line = (
        incident["police_tip_line"] if "police_tip_line" in incident else None
    )
    new_incident.help_the_victim = (
        incident["help_the_victim"] if "help_the_victim" in incident else None
    )

    incident_id = new_incident.upsert().id
    if incident_id:
        if to_flush_cache:
            flush_cache()
        return incident_id
    else:
        raise SystemError("Failed to upsert the incident with id:" + new_incident.id)


# Query incidents within the given dates and state
# Return [ { key: date, value : count, incident_location: state } ]


@cached(cache=INCIDENT_STATS_CACHE)
def getStats(start: datetime, end: datetime, state=""):
    stats = {}  # (date, state) : count
    for incident in queryIncidents(start, end, state):
        incident_date = incident["incident_time"].strftime("%Y-%m-%d")
        key = (incident_date, incident["incident_location"])
        if key not in stats:
            stats[key] = 0
        stats[key] += 1

    ret = []
    for key in stats:
        (date, state) = key
        ret.append({"key": date, "incident_location": state, "value": stats[key]})

    return ret


def insertUserReport(user_report, to_flush_cache=True):
    # return user_report id
    new_user_report = UserReport(
        user_report_time=(
            dateparser.parse(user_report["user_report_time"])
            if isinstance(user_report["user_report_time"], str)
            else user_report["user_report_time"]
        ),
        user_report_location=user_report["user_report_location"],
        description=user_report["description"],
        attachments=user_report["attachments"]
    )

    new_user_report.id = user_report["id"] if "id" in user_report else None
    new_user_report.description_translate = (
        user_report["description_translate"]
        if "description_translate" in user_report
        else {}
    )
    new_user_report.status = (
        str(user_report["status"]) if "status" in user_report else None
    )
    new_user_report.approved_by = (
        user_report["created_by"] if "created_by" in user_report else None
    )
    new_user_report.email = user_report["email"] if "email" in user_report else None
    new_user_report.phone = user_report["phone"] if "phone" in user_report else None
    new_user_report.publish_status = (
        user_report["publish_status"] if "publish_status" in user_report else {}
    )
    new_user_report.donation_link = (
        user_report["donation_link"] if "donation_link" in user_report else None
    )
    new_user_report.police_tip_line = (
        user_report["police_tip_line"] if "police_tip_line" in user_report else None
    )
    new_user_report.help_the_victim = (
        user_report["help_the_victim"] if "help_the_victim" in user_report else None
    )

    user_report_id = new_user_report.upsert().id
    if user_report_id:
        if to_flush_cache:
            flush_cache()
        return user_report_id
    else:
        raise SystemError(
            "Failed to upsert the user_report with id:" + new_user_report.id
        )

def updateUserReport(user_report):
    # Initialize Firestore client
    db = firestore.Client()

    def get_user_report_by_report_id(report_id):
        # Query for the document with the specified report_id
        doc_ref = db.collection('incident').document(report_id)
        doc = doc_ref.get()
        # Iterate over the query results and return the first match
        if doc.exists:
            return doc.id, doc.to_dict()  # Return both the document ID and its data
        # If no match found, return None
        return None, None

    try:
        # Get the document ID and the user report data
        doc_id, existing_report = get_user_report_by_report_id(user_report["report_id"])

        if doc_id is None:
            return {"error": "Report ID not found", "report_id": user_report["report_id"]}, 404  # Return an error if the report_id does not exist

        # Reference to the specific document to update
        user_report_ref = db.collection('incident').document(doc_id)

        # Update the document with the new details
        updates = {}
        if user_report.get("contact_name"):
            updates['contact_name'] = user_report["contact_name"]
        if user_report.get("email"):
            updates['email'] = user_report["email"]
        if user_report.get("phone"):
            updates['phone'] = user_report["phone"]
        if user_report.get("status"):
            updates['status'] = user_report["status"]

        if updates:
            user_report_ref.update(updates)

        # Return the report_id in the response
        return {'report_id': user_report["report_id"]}, 200
    
    except Exception as e:
        print(f"Error updating user report: {str(e)}")  # Log the error
        return {"error": "Failed to update user report", "details": str(e)}, 500

@cached(cache=INCIDENT_CACHE)
def queryUserReports(start: datetime, end: datetime, state=""):
    end_time = datetime(end.year, end.month, end.day, 23, 59, 59)
    query = UserReport.collection.filter("user_report_time", ">=", start).filter(
        "user_report_time", "<=", end_time
    )
    if state != "":
        query = query.filter("user_report_location", "==", state)

    result = query.order("-user_report_time").fetch()
    return [user_report.to_dict() for user_report in result]


def deleteUserReport(user_report_id):
    if UserReport.collection.delete("user_report/" + user_report_id):
        flush_cache()
        return True
    return False

def getUserReports(start: datetime, end: datetime, state="", skip_cache=False):
    if skip_cache:
        INCIDENT_CACHE.clear()
    return queryUserReports(start, end, state)

def getAllIncidents(params, user_role):
    """
    Fetches all incidents based on query parameters and user role.
    
    Args:
    - params (dict): Query parameters
    - user_role (str): The role of the user ('admin' or 'viewer')
    
    Returns:
    - (dict, int): Response and HTTP status code
    """
    # Validate query parameters
    validation_error = get_all_validation(params, user_role)
    if validation_error:
        return validation_error
    
    # Your existing logic to fetch incidents...
    incidents = []  # Replace with actual fetching logic

    return {
        "page_info": {
            "start_row": 0,
            "page_size": 10,
            "total_records": len(incidents),
            "next_page_token": None
        },
        "incidents": incidents
    }
    
def get_incident_by_id(report_id):
    try:
        # Initialize Firestore client
        db = firestore.Client()

        # Get document reference and attempt to fetch
        doc_ref = db.collection('incident').document(report_id)
        doc = doc_ref.get()
        
        # Check if document exists
        if not doc.exists:
            return {"error": "Report ID not found", "report_id": report_id}, 404
            
        # Return successful response
        return doc.to_dict(), 200
        
    except Exception as e:
        print(f"Error getting incident by ID: {str(e)}")  # Log the error
        return {"error": "Failed to get incident", "details": str(e)}, 500