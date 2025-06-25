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

def get_query_cache_key(*args, **kwargs):
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

def _should_include_incident(doc_dict, incident_type, self_report_status):
    """Determines whether a document should be included based on type and status filters.
    
    Applies filtering logic for different incident types, with special handling for:
    - Mixed type filtering ("both")
    - Self-report status verification
    - Legacy document support (default type)

    Args:
        doc_dict: The Firestore document dictionary containing incident data
        incident_type: The requested incident type filter. Possible values:
                      "news", "self_report", "both", or "" (empty string)
        self_report_status: Status filter for self-reported incidents. Possible values:
                           "approved", "pending", "rejected", "all", or None/"" 

    Returns:
        bool: True if the document matches all filter criteria, False otherwise

    Behavior Details:
        - When incident_type is "both" or empty:
            * Always includes news documents
            * Applies status filtering to self-reports
        - For specific types ("news"/"self_report"):
            * Strict type matching required
            * Additional status filtering for self-reports
        - Empty self_report_status defaults to "approved"
        - Missing document type defaults to "news" (legacy support)
    """
    doc_type = doc_dict.get('type', 'news')  # Default to 'news' for legacy
    selfreport_filter_status = "approved" if self_report_status == "" else self_report_status
    
    if incident_type == "both" or incident_type == "":
        if doc_type == "self_report":
            return selfreport_filter_status == "all" or doc_dict.get('self_report_status') == selfreport_filter_status
        return True  # Always include news when type="both"
    
    if incident_type != doc_type:
        return False

    if incident_type == 'self_report':
        return selfreport_filter_status == "all" or doc_dict.get('self_report_status') == selfreport_filter_status

    return True

def _get_pagination_info(db, collection_name, first_result, last_result, start, end, state, incident_type, self_report_status):
    """Determines pagination information by checking for adjacent documents.
    
    Checks whether there are more results before and after the current page by executing minimal queries 
    against Firestore, applying all relevant filters. This is more efficient than fetching all results.

    Args:
        db: Firestore client instance for database operations
        collection_name: Name of the collection to query in Firestore
        first_result: The first document in the current pagination window (for prev check), or None if at start
        last_result: The last document in the current pagination window (for next check), or None if at end
        start: Unix timestamp (inclusive) for start of time filter range
        end: Unix timestamp (inclusive) for end of time filter range
        state: Optional U.S. state abbreviation or CANADA to filter by incident_location, or None for no state filter
        incident_type: Incident type filter ('news', 'self_report', etc.)
        self_report_status: Optional status filter for self-reported incidents, or None for no status filter

    Returns:
        A tuple of two booleans:
        - has_next: True if documents exist after current page matching all filters
        - has_prev: True if documents exist before current page matching all filters
    """
    has_next = has_prev = False
    
    # Check for next page - look ahead up to 100 documents to find a valid one
    if last_result:
        next_query = db.collection(collection_name)
        if start: next_query = next_query.where("incident_time", ">=", start)
        if end: next_query = next_query.where("incident_time", "<=", end)
        if state: next_query = next_query.where("incident_location", "==", state)
        next_query = next_query.order_by("incident_time", direction=firestore.Query.DESCENDING)
        next_query = next_query.start_after(db.collection(collection_name).document(last_result['id']).get())
        next_query = next_query.limit(100)  # Look ahead up to 100 documents
        
        for doc in next_query.stream():
            if _should_include_incident(doc.to_dict(), incident_type, self_report_status):
                has_next = True
                break
    
    # Check for previous page - look back up to 100 documents to find a valid one
    if first_result:
        prev_query = db.collection(collection_name)
        if start: prev_query = prev_query.where("incident_time", ">=", start)
        if end: prev_query = prev_query.where("incident_time", "<=", end)
        if state: prev_query = prev_query.where("incident_location", "==", state)
        prev_query = prev_query.order_by("incident_time", direction=firestore.Query.DESCENDING)
        prev_query = prev_query.end_before(db.collection(collection_name).document(first_result['id']).get())
        prev_query = prev_query.limit(100)  # Look back up to 100 documents
        
        for doc in prev_query.stream():
            if _should_include_incident(doc.to_dict(), incident_type, self_report_status):
                has_prev = True
                break
    
    return has_next, has_prev

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
    if end: end_time = datetime(end.year, end.month, end.day, 23, 59, 59)
    
    db = firestore.Client()
    collection_name = Incident.Meta.collection_name
    
    # Base query
    query = db.collection(collection_name)
    if start: query = query.where("incident_time", ">=", start)
    if end_time: query = query.where("incident_time", "<=", end_time)
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
        
    return queryIncidents(start, end, state, type, self_report_status, page_size, cursor, direction)


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
    # Create user report incident with required fields, returns the incident id
    new_user_report = Incident(
        incident_time=(
            dateparser.parse(user_report["incident_time"])
            if isinstance(user_report["incident_time"], str)
            else user_report["incident_time"]
        ),
        incident_location=user_report["incident_location"],
        abstract=user_report["abstract"],
        attachments= user_report.get("attachments", None)  # Not required but it's an input from the frontend, it's an array of strings for GCS
    )
    
    # Set incident type
    new_user_report.type = "self_report"
    
    # Optional fields
    new_user_report.self_report_status = "new"
    new_user_report.abstract_translate = user_report.get("abstract_translate", {})
    new_user_report.approved_by = None
    new_user_report.contact_name = user_report.get("contact_name", None)
    new_user_report.email = user_report.get("email", None)
    new_user_report.phone = user_report.get("phone", None)
    new_user_report.publish_status = {}

    user_report_id = new_user_report.insert().id
    if user_report_id:
        if to_flush_cache:
            flush_cache()
        return user_report_id
    raise SystemError(
        "Failed to insert the user_report with id:" + new_user_report.id
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
        updates['approved_by'] = user_report["approved_by"]

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
    start = params.get('start', datetime.now() - timedelta(years=1))
    end = params.get('end', datetime.now())
    state = params.get('state', '')
    incident_type = params.get('type', 'both')
    self_report_status = params.get('self_report_status', 'approved')
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
