import os
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
    incident_time = mdl.DateTime(required=True)
    incident_location = mdl.TextField()
    type = mdl.TextField()
    self_report_status = mdl.TextField(required=False)
    class Meta:
        abstract = True  # Mark this model as abstract


class UserReport(BaseReport):
    description = mdl.TextField(required=False)
    description_translate = mdl.MapField(required=False)
    attachments = mdl.TextField(required=False)
    status = mdl.TextField(required=False)
    approved_by = mdl.TextField(required=False)
    report_id = mdl.ListField(required=False)
    contact_name = mdl.TextField(required=False)
    email = mdl.TextField(required=False)
    phone = mdl.TextField(required=False)
    class Meta:
        # If you want to use a different collection:
        # Before running the app, set with: export FIRESTORE_COLLECTION=your_test_collection
        # If running with run.sh, the collection name is set in the run.sh script
        collection_name = os.getenv('FIRESTORE_COLLECTION', 'incident')  # Default to 'incident'


class Incident(BaseReport):
    abstract = mdl.TextField(required=False)
    abstract_translate = mdl.MapField(required=False)
    url = mdl.TextField(required=False)
    incident_source = mdl.TextField(required=False)
    created_by = mdl.TextField(required=False)
    title = mdl.TextField(required=False)
    title_translate = mdl.MapField(required=False)
    parent_doc = mdl.TextField(column_name="parent")
    class Meta:
        collection_name = os.getenv('FIRESTORE_COLLECTION', 'incident')


VALID_SELF_REPORT_STATUSES = {"all", "approved", "rejected", "new"}
VALID_TYPE_STATUSES = {"news", "self_report", "both"}

@cached(cache=INCIDENT_CACHE)
def queryIncidents(start: datetime, end: datetime, state="", type="", self_report_status="", page_size=10, last_doc=None):
    # Validate inputs
    if self_report_status not in VALID_SELF_REPORT_STATUSES:
        return {"error": f"Invalid self_report_status: {self_report_status}. Allowed values are {VALID_SELF_REPORT_STATUSES}"}
    
    if type not in VALID_TYPE_STATUSES:
        return {"error": f"Invalid type: {type}. Allowed values are {VALID_TYPE_STATUSES}"}
    
    # Ensure page_size is valid
    try:
        page_size = int(page_size) if str(page_size).isdigit() and int(page_size) > 0 else 10
    except ValueError:
        page_size = 10  # Default value
    
    # Set end time to end of day
    end_time = datetime(end.year, end.month, end.day, 23, 59, 59)
    
    # Base query with date range filter
    query = Incident.collection.filter("incident_time", ">=", start).filter(
        "incident_time", "<=", end_time
    )
    
    # Add state filter if provided
    if state:
        query = query.filter("incident_location", "==", state)
    
    # Order by incident_time in descending order
    query = query.order("-incident_time")
    
    # Apply cursor pagination if last_doc is provided and is a valid document reference
    if last_doc and hasattr(last_doc, 'id'):
        query = query.start_after(last_doc)
    
    # Apply page size limit
    query = query.limit(page_size)
    
    # Execute query and get results
    incidents = []
    last_incident = None
    
    if type == "both":
        # If self_report_status is specified and not "all",
        # we need to handle the news and self_report separately and add a filter to self_report
        if self_report_status and self_report_status != "all":
            # For news incidents: type is null, empty or "news"
            news_query = query.filter("type", "in", [None, "", "news"])
            news_incidents = list(news_query.fetch())
            
            # For self-reports: type is "self_report" AND status matches
            self_report_query = query.filter("type", "==", "self_report").filter("self_report_status", "==", self_report_status)
            self_report_incidents = list(self_report_query.fetch())
            
            incidents = sorted(news_incidents + self_report_incidents, key=lambda x: x.incident_time, reverse=True)[:page_size]
        else:
            # If no status filter, we can get all incidents
            incidents = list(query.fetch())[:page_size]
        
    elif type == "self_report":
        query = query.filter("type", "==", "self_report")
        if self_report_status and self_report_status != "all":
            query = query.filter("self_report_status", "==", self_report_status)
        incidents = list(query.fetch())
        
    elif type == "news":
        # Fetch all incidents matching our base criteria
        all_incidents = list(query.fetch())
        # Filter for news incidents (type is None, empty, or "news")
        incidents = [i for i in all_incidents if not hasattr(i, "type") or i.type in [None, "", "news"]]
    
    # Get the last incident for pagination if we have results
    if incidents:
        last_incident = incidents[-1]
    
    return {
        "incidents": [incident.to_dict() for incident in incidents],
        "last_doc": last_incident
    }


def deleteIncident(incident_id):
    if Incident.collection.delete("incident/" + incident_id):
        flush_cache()
        return True
    return False

def getIncidents(start: datetime, end: datetime, state="", type="", self_report_status="", start_row=None, page_size=10, skip_cache=False):
    if skip_cache:
        INCIDENT_CACHE.clear()
    
    # Convert start_row to a document reference if needed
    last_doc = None
    if start_row and isinstance(start_row, str) and start_row != "":
        # If start_row is a document ID, get the document reference
        try:
            last_doc = Incident.collection.get(start_row)
        except:
            # If document lookup fails, continue without pagination
            pass
    
    result = queryIncidents(start, end, state, type, self_report_status, page_size, last_doc)
    
    # Extract just the incidents list from the result
    if isinstance(result, dict) and "incidents" in result:
        return result["incidents"]
    return result


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
    if user_report["type"] not in VALID_TYPE_STATUSES:
        return {"error": "Invalid type value"}, 400
    # return user_report id
    new_user_report = UserReport(
        incident_time=(
            dateparser.parse(user_report["incident_time"])
            if isinstance(user_report["incident_time"], str)
            else user_report["incident_time"]
        ),
        incident_location=user_report["incident_location"],
        description=user_report["description"],
        attachments=user_report["attachments"]
    )
    new_user_report.type = "self_report"
    new_user_report.self_report_status = user_report["self_report_status"] if "self_report_status" in user_report else None
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


def deleteUserReport(user_report_id):
    if UserReport.collection.delete("user_report/" + user_report_id):
        flush_cache()
        return True
    return False

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

# Log for checking the firesotre colection name in use
def verify_collection():
    collection_name = os.getenv('FIRESTORE_COLLECTION', 'incident')
    print(f"Using collection: {collection_name}")
    # Example query to verify
    db = firestore.Client()
    docs = db.collection(collection_name).limit(1).stream()
    for doc in docs:
        print(f"Document in collection: {doc.id}")

verify_collection()