import os
from datetime import datetime

import dateparser
from cachetools import cached
from fireo import models as mdl

from google.cloud import firestore
from firestore.cachemanager import INCIDENT_CACHE, INCIDENT_STATS_CACHE, flush_cache
from firestore.get_all_validation import get_all_validation

VALID_SELF_REPORT_STATUSES = {"approved", "rejected", "new"}
VALID_QUERY_SELF_REPORT_STATUSES = VALID_SELF_REPORT_STATUSES | {"all"}

VALID_INCIDENT_TYPES = {"news", "self_report"}
VALID_QUERY_INCIDENT_TYPES = VALID_INCIDENT_TYPES | {"both"}

class Incident(mdl.Model):
    created_on = mdl.DateTime(auto=True)
    publish_status = mdl.MapField(
        required=True, default={"twitter": None, "linkedin": None, "notification": None}
    )
    donation_link = mdl.TextField()  # Link to donation website
    police_tip_line = mdl.TextField()  # Phone number to provide tips to police
    help_the_victim = mdl.TextField()  # Text about how people can help the victim
    incident_time = mdl.DateTime(required=True)
    incident_location = mdl.TextField(required=True)
    abstract = mdl.TextField(required=True)
    abstract_translate = mdl.MapField(required=False)
    type = mdl.TextField()
    parent_doc = mdl.TextField(column_name="parent")


    #news incident data
    url = mdl.TextField(required=False)
    incident_source = mdl.TextField(required=False)
    created_by = mdl.TextField(required=False)
    title = mdl.TextField(required=False)
    title_translate = mdl.MapField(required=False)
    
    # self-report incident data
    attachments = mdl.ListField(required=False)
    self_report_status = mdl.TextField(required=True, default="new")
    approved_by = mdl.TextField(required=False)
    contact_name = mdl.TextField(required=False)
    email = mdl.TextField(required=False)
    phone = mdl.TextField(required=False)
    class Meta:
        collection_name = os.getenv('FIRESTORE_COLLECTION', 'incident')  # Default to 'incident'



@cached(cache=INCIDENT_CACHE)
def queryIncidents(start: datetime, end: datetime, state="", type="", self_report_status="", start_row="", page_size=""):
    # Convert start_row and page_size to integers
    # TODO: implement the pagination based on Firestore (https://firebase.google.com/docs/firestore/query-data/query-cursors)
    try:
        # Validate type and self_report_status
        self_report_status = "approved" if self_report_status == "" else self_report_status
        if self_report_status not in VALID_QUERY_SELF_REPORT_STATUSES:
            return {"error": f"Invalid self_report_status: {self_report_status}. Allowed values are {VALID_QUERY_SELF_REPORT_STATUSES}"}
        type="both" if type == "" else type
        if type not in VALID_QUERY_INCIDENT_TYPES:
            return {"error": f"Invalid data type: {type}. Allowed values are {VALID_QUERY_INCIDENT_TYPES}"}
        start_row = int(start_row) if str(start_row).isdigit() and int(start_row) >= 0 else 0
        page_size = int(page_size) if str(page_size).isdigit() and int(page_size) > 0 else 1000
    except ValueError:
        start_row, page_size = 0, 10  # Default values
    
    end_time = datetime(end.year, end.month, end.day, 23, 59, 59)
    query = Incident.collection.filter("incident_time", ">=", start).filter(
        "incident_time", "<=", end_time
    )
    if state != "":
        query = query.filter("incident_location", "==", state)

    incidents = []

    if type == "both":
        all_incidents = list(query.fetch())
        # Split into news and self_report incidents based on type
        news_incidents = [i for i in all_incidents if i.type == "news"]
        self_report_incidents = [i for i in all_incidents if i.type == "self_report"]
        # For self-reports, only show approved ones unless explicitly requested
        if not self_report_status:
            self_report_incidents = [i for i in self_report_incidents if i.self_report_status == "approved"]
        elif self_report_status != "approved":
            # If requesting non-approved status, we need to check admin permissions in main.py
            self_report_incidents = [i for i in self_report_incidents if i.self_report_status == self_report_status]
        # Merge both queries
        incidents = sorted(news_incidents + self_report_incidents, key=lambda x: x.incident_time, reverse=True)

    else:
        if type == "self_report":
            query = query.filter("type", "==", "self_report")
            if self_report_status:
                query = query.filter("self_report_status", "==", self_report_status)
        elif type == "news":
            query = query.filter("type", "==", "news")

        incidents = list(query.order("-incident_time").fetch())  # Fetch incidents

    # Apply pagination. If the value of start_row/page_size is greater than the length of incidents, return [] (empty set).
    if start_row > 0:
        incidents = incidents[start_row:]  # Skip first start_row items
    if page_size:
        incidents = incidents[:page_size]  # Limit results to page_size

    # Convert all incidents to dictionaries
    return [incident.to_dict() for incident in incidents] if incidents else []


def deleteIncident(incident_id):
    if Incident.collection.delete("incident/" + incident_id):
        flush_cache()
        return True
    return False


def getIncidents(start: datetime, end: datetime, state="", type="", self_report_status="", start_row="", page_size="", skip_cache=False):
    if skip_cache:
        INCIDENT_CACHE.clear()
    return queryIncidents(start, end, state, type, self_report_status, start_row, page_size)


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
def getStats(start: datetime, end: datetime, state="", type="", self_report_status=""):
    stats = {}  # (date, state) : {"news": count, "self_report": count}
    incidents = queryIncidents(start, end, state, type, self_report_status)
    
    # Check if we got an error response
    if isinstance(incidents, dict) and "error" in incidents:
        return []
        
    for incident in incidents:
        # Handle both string and datetime inputs
        incident_time = incident["incident_time"]
        if isinstance(incident_time, str):
            incident_time = dateparser.parse(incident_time)
        incident_date = incident_time.strftime("%Y-%m-%d")
        key = (incident_date, incident["incident_location"])
        
        if key not in stats:
            stats[key] = {"news": 0, "self_report": 0}
        
        # Count the incidents by type for frontend display
        incident_type = incident.get("type", "news")  # Default to news if type not specified
        if incident_type == "self_report":
            stats[key]["self_report"] += 1
        else:
            stats[key]["news"] += 1

    ret = []
    for key in stats:
        (date, state) = key
        ret.append({
            "key": date,
            "incident_location": state,
            "news": stats[key]["news"],
            "self_report": stats[key]["self_report"]
        })

    return ret


def insertUserReport(user_report, to_flush_cache=True):
    if user_report["self_report_status"] not in VALID_SELF_REPORT_STATUSES:
        return {"error": "Invalid self_report_status value"}, 400
    
    # Create user report incident with required fields, returns the incident id
    new_user_report = Incident(
        incident_time=(
            dateparser.parse(user_report["incident_time"])
            if isinstance(user_report["incident_time"], str)
            else user_report["incident_time"]
        ),
        incident_location=user_report["incident_location"],
        abstract=user_report["abstract"],
        attachments= user_report.get("attachments", [])  # Not required but it's an input from the frontend, it's an array of strings for GCS
    )
    
    # Set incident type
    new_user_report.type = "self_report"
    
    # Optional fields
    new_user_report.id = user_report.get("id", None)
    new_user_report.self_report_status = user_report.get("self_report_status", "new")
    new_user_report.abstract_translate = user_report.get("abstract_translate", {})
    new_user_report.approved_by = user_report.get("approved_by", None)
    new_user_report.contact_name = user_report.get("contact_name", None)
    new_user_report.email = user_report.get("email", None)
    new_user_report.phone = user_report.get("phone", None)
    new_user_report.publish_status = user_report.get("publish_status", {})
    new_user_report.donation_link = user_report.get("donation_link", None)
    new_user_report.police_tip_line = user_report.get("police_tip_line", None)
    new_user_report.help_the_victim = user_report.get("help_the_victim", None)

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
        # User updates fields
        if user_report.get("contact_name"):
            updates['contact_name'] = user_report["contact_name"]
        if user_report.get("email"):
            updates['email'] = user_report["email"]
        if user_report.get("phone"):
            updates['phone'] = user_report["phone"]
            
        # Admin updates fields
        if user_report.get("self_report_status"):
            if user_report["self_report_status"] not in VALID_SELF_REPORT_STATUSES:
                return {"error": "Invalid self_report_status value"}, 400
            updates['self_report_status'] = user_report["self_report_status"]
        if user_report.get("approved_by"):
            updates['approved_by'] = user_report["approved_by"]
        if user_report.get("donation_link"):
            updates['donation_link'] = user_report["donation_link"]
        if user_report.get("police_tip_line"):
            updates['police_tip_line'] = user_report["police_tip_line"]
        if user_report.get("help_the_victim"):
            updates['help_the_victim'] = user_report["help_the_victim"]

        if updates:
            user_report_ref.update(updates)
            flush_cache()  # Clear cache after updating

        # Return the report_id in the response
        return {'report_id': user_report["report_id"]}, 200
    
    except Exception as e:
        print(f"Error updating user report: {str(e)}")  # Log the error
        return {"error": "Failed to update user report", "details": str(e)}, 500


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
        db = firestore.Client()
        doc_ref = db.collection('incident').document(report_id)
        doc = doc_ref.get()
        if not doc.exists:
            return {"error": "Report ID not found", "report_id": report_id}, 404
        return doc.to_dict(), 200
    except Exception as e:
        print(f"Error getting incident by ID: {str(e)}") 
        return {"error": "Failed to get incident", "details": str(e)}, 500
