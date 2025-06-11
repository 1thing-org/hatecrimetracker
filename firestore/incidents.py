import os
from datetime import datetime

import dateparser
from cachetools import cached
from fireo import models as mdl

from google.cloud import firestore
from firestore.cachemanager import INCIDENT_CACHE, INCIDENT_STATS_CACHE, flush_cache
from firestore.get_all_validation import get_all_validation

VALID_SELF_REPORT_STATUSES = {"approved", "rejected", "new"}
VALID_QUERY_SELF_REPORT_STATUSES = VALID_SELF_REPORT_STATUSES | {"", "all"}

VALID_INCIDENT_TYPES = {"news", "self_report"}
VALID_QUERY_INCIDENT_TYPES = VALID_INCIDENT_TYPES | {"", "both"}

def _should_include_incident(doc_dict, incident_type, self_report_status):
    """Determine if an incident should be included based on filters"""
    doc_type = doc_dict.get('type', 'news')  # Default to 'news' for legacy
    
    if incident_type == "both":
        if doc_type == "self_report":
            filter_status = "approved" if self_report_status == "" else self_report_status
            return filter_status == "all" or doc_dict.get('self_report_status') == filter_status
        return True  # Always include news when type="both"
    
    if incident_type == "self_report" and doc_type != "self_report":
        return False
    if incident_type == "news" and doc_type == "self_report":
        return False
    
    if (incident_type != "news" and self_report_status and self_report_status != "all" and
        doc_type == "self_report" and doc_dict.get('self_report_status') != self_report_status):
        return False
    
    return True

def _get_pagination_info(db, collection_name, first_result, last_result, start, end, state, incident_type, self_report_status):
    """Determine pagination info more efficiently"""
    has_next = has_prev = False
    
    # Check for next page
    if last_result:
        next_query = db.collection(collection_name)
        next_query = next_query.where("incident_time", ">=", start)
        next_query = next_query.where("incident_time", "<=", end)
        if state: next_query = next_query.where("incident_location", "==", state)
        next_query = next_query.order_by("incident_time", direction=firestore.Query.DESCENDING)
        next_query = next_query.start_after(db.collection(collection_name).document(last_result['id']).get())
        next_query = next_query.limit(1)
        
        for doc in next_query.stream():
            if _should_include_incident(doc.to_dict(), incident_type, self_report_status):
                has_next = True
                break
    
    # Check for previous page
    if first_result:
        prev_query = db.collection(collection_name)
        prev_query = prev_query.where("incident_time", ">=", start)
        prev_query = prev_query.where("incident_time", "<=", end)
        if state: prev_query = prev_query.where("incident_location", "==", state)
        prev_query = prev_query.order_by("incident_time", direction=firestore.Query.DESCENDING)
        prev_query = prev_query.end_before(db.collection(collection_name).document(first_result['id']).get())
        prev_query = prev_query.limit(1)
        
        for doc in prev_query.stream():
            if _should_include_incident(doc.to_dict(), incident_type, self_report_status):
                has_prev = True
                break
    
    return has_next, has_prev

def get_query_cache_key(*args, **kwargs):
    """Custom cache key function that handles non-hashable types like dictionaries"""
    # Convert args to a list for modification
    args_list = list(args)
    
    # Check if we have a cursor parameter (index 6)
    if len(args_list) > 6 and isinstance(args_list[6], dict):
        cursor = args_list[6]
        if cursor:
            # Convert the cursor dict to a hashable string representation
            cursor_str = f"cursor:{cursor.get('id', 'none')}"
            args_list[6] = cursor_str
    
    # Check if we have a direction parameter (index 7)
    if len(args_list) > 7:
        # Direction is already a string, so it's hashable
        pass
    
    # Convert back to tuple and return with kwargs
    return tuple(args_list), frozenset(sorted(kwargs.items()))

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

@cached(cache=INCIDENT_CACHE, key=get_query_cache_key)
def queryIncidents(start: datetime, end: datetime, state="", type="", self_report_status="", page_size=10, cursor=None, direction="forward"):
    # Validate inputs
    if self_report_status not in VALID_QUERY_SELF_REPORT_STATUSES:
        return {"error": f"Invalid self_report_status: {self_report_status}. Allowed values are {VALID_QUERY_SELF_REPORT_STATUSES}"}
    
    if type not in VALID_QUERY_INCIDENT_TYPES:
        return {"error": f"Invalid type: {type}. Allowed values are {VALID_QUERY_INCIDENT_TYPES}"}
    
    try:
        page_size = int(page_size) if str(page_size).isdigit() and int(page_size) > 0 else 10
    except ValueError:
        page_size = 10
    
    # Set end time to end of day
    end_time = datetime(end.year, end.month, end.day, 23, 59, 59)
    
    db = firestore.Client()
    collection_name = Incident.Meta.collection_name
    
    # Base query
    query = db.collection(collection_name)
    query = query.where("incident_time", ">=", start)
    query = query.where("incident_time", "<=", end_time)
    if state: query = query.where("incident_location", "==", state)
    
    # Handle direction
    if direction == "backward":
        query = query.order_by("incident_time")
    else:
        query = query.order_by("incident_time", direction=firestore.Query.DESCENDING)
    
    # Handle cursor
    if cursor and cursor.get('id'):
        cursor_doc = db.collection(collection_name).document(cursor['id']).get()
        if cursor_doc.exists:
            query = query.start_after(cursor_doc)
    
    # Fetch one extra to check for more results
    query = query.limit(page_size + 1)
    
    # Process results
    results = []
    for doc in query.stream():
        doc_dict = doc.to_dict()
        doc_dict['id'] = doc.id
        if _should_include_incident(doc_dict, type, self_report_status):
            results.append(doc_dict)
    
    # Handle backward direction
    if direction == "backward":
        results.reverse()
    
    # Determine pagination
    has_more = len(results) > page_size
    results = results[:page_size]
    
    first_doc = results[0] if results else None
    last_doc = results[-1] if results else None
    
    # Get pagination info
    has_next, has_prev = _get_pagination_info(
        db, collection_name, first_doc, last_doc, 
        start, end_time, state, type, self_report_status
    )
    
    return {
        "incidents": results,
        "pagination": {
            "has_next": has_next,
            "has_prev": has_prev,
            "next_cursor": {"id": last_doc['id']} if last_doc and has_next else None,
            "prev_cursor": {"id": first_doc['id']} if first_doc and has_prev else None,
            "page_size": page_size,
            "count": len(results)
        }
    }


def deleteIncident(incident_id):
    if Incident.collection.delete("incident/" + incident_id):
        flush_cache()
        return True
    return False

def getIncidents(start: datetime, end: datetime, state="", type="", self_report_status="", cursor=None, direction="forward", page_size=10, skip_cache=False):
    if skip_cache:
        INCIDENT_CACHE.clear()
    
    # Convert cursor if it's a string
    if cursor and isinstance(cursor, str) and cursor != "":
        cursor = {'id': cursor}
    
    result = queryIncidents(start, end, state, type, self_report_status, page_size, cursor, direction)
    
    # If we got an error response, return it directly
    if isinstance(result, dict) and "error" in result:
        return result
        
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
    
    db = firestore.Client()
    collection_name = Incident.Meta.collection_name
    end_time = datetime(end.year, end.month, end.day, 23, 59, 59)
    
    query = db.collection(collection_name)
    query = query.where("incident_time", ">=", start)
    query = query.where("incident_time", "<=", end_time)
    if state: query = query.where("incident_location", "==", state)
    
    for doc in query.stream():
        doc_dict = doc.to_dict()
        if _should_include_incident(doc_dict, type, self_report_status):
            incident_time = doc_dict["incident_time"]
            if isinstance(incident_time, str):
                incident_time = dateparser.parse(incident_time)
            incident_date = incident_time.strftime("%Y-%m-%d")
            key = (incident_date, doc_dict["incident_location"])
            
            if key not in stats:
                stats[key] = {"news": 0, "self_report": 0}
            
            if doc_dict.get('type') == "self_report":
                stats[key]["self_report"] += 1
            else:
                stats[key]["news"] += 1

    return [{
        "key": date,
        "incident_location": state,
        "news": counts["news"],
        "self_report": counts["self_report"]
    } for (date, state), counts in stats.items()]


def insertUserReport(user_report, to_flush_cache=True):
    if user_report["self_report_status"] not in VALID_SELF_REPORT_STATUSES:
        return {"error": "Invalid self_report_status value"}, 400
    # return user_report id
    new_user_report = Incident(
        incident_time=(
            dateparser.parse(user_report["incident_time"])
            if isinstance(user_report["incident_time"], str)
            else user_report["incident_time"]
        ),
        incident_location=user_report["incident_location"],
        abstract=user_report["abstract"],
        attachments= user_report["attachments"] if "self_report_status" in user_report else []
    )
    new_user_report.type = "self_report"
    new_user_report.self_report_status = user_report["self_report_status"] if "self_report_status" in user_report else "new"
    new_user_report.id = user_report["id"] if "id" in user_report else None
    new_user_report.abstract_translate = (
        user_report["abstract_translate"]
        if "abstract_translate" in user_report
        else {}
    )
    new_user_report.status = (
        str(user_report["status"]) if "status" in user_report else None
    )
    new_user_report.email = user_report["email"] if "email" in user_report else None
    new_user_report.phone = user_report["phone"] if "phone" in user_report else None
    new_user_report.publish_status = (
        user_report["publish_status"] if "publish_status" in user_report else {}
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


def getAllIncidents(params, user_role):
    """
    Fetches all incidents based on query parameters and user role.
    
    Args:
        params (dict): Query parameters including:
            - start: Start datetime (default: 30 days ago)
            - end: End datetime (default: now)
            - state: State filter (optional)
            - type: Incident type filter (optional)
            - self_report_status: Status filter (optional)
            - page_size: Results per page (default: 10, max: 100)
            - cursor: Pagination cursor (optional)
            - direction: Pagination direction (forward/backward)
        user_role (str): User role ('admin' or 'viewer')
    
    Returns:
        dict: Response with incidents and pagination info
        int: HTTP status code
    """
    validation_error = get_all_validation(params, user_role)
    if validation_error:
        return validation_error
    
    # Set defaults
    start = params.get('start', datetime.now() - timedelta(days=30))
    end = params.get('end', datetime.now())
    state = params.get('state', '')
    incident_type = params.get('type', 'both')
    self_report_status = params.get('self_report_status', 'approved' if user_role != 'admin' else 'all')
    page_size = min(int(params.get('page_size', 10)), 100)
    cursor = params.get('cursor')
    direction = params.get('direction', 'forward')
    
    result = queryIncidents(
        start=start,
        end=end,
        state=state,
        type=incident_type,
        self_report_status=self_report_status,
        page_size=page_size,
        cursor=cursor,
        direction=direction
    )
    
    if isinstance(result, dict) and "error" in result:
        return result, 400
    
    return {
        "page_info": {
            "start_row": 0,
            "page_size": len(result["incidents"]),
            "total_records": -1,  # Consider adding count query if needed
            "next_page_token": result["pagination"]["next_cursor"]["id"] if result["pagination"]["next_cursor"] else None
        },
        "incidents": result["incidents"]
    }, 200
    
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
