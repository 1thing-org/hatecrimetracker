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


def upsert_incident(incident_data: dict, to_flush_cache=True):
    """
    Creates or updates an incident. If 'id' is in incident_data, it updates.
    Otherwise, it creates a new incident.
    Handles both 'news' and 'self_report' types.
    """
    incident_id = incident_data.get("id")
    incident_type = incident_data.get("type", "news")

    # # Check required fields from the model definition for all operations
    # required_fields = []
    # for field_name, field_obj in Incident.Meta.fields.items():
    #     # FireO's `required` flag
    #     if getattr(field_obj, 'required', False):
    #         # Skip fields with default values
    #         if getattr(field_obj, 'default', None) is None:
    #             # For new incidents, field must be present. For updates, if present, it cannot be null.
    #             if not incident_id and field_name not in incident_data:
    #                  required_fields.append(field_name)
    #             elif field_name in incident_data and incident_data[field_name] is None:
    #                  raise ValueError(f"Required field '{field_name}' cannot be set to null.")
    # if required_fields:
    #     raise ValueError(f"Missing required fields for new incident: {', '.join(required_fields)}")

    # Conditional validation for 'news' type
    if incident_type == 'news':
        news_required_fields = ['url', 'incident_source', 'created_by', 'title']
        missing_news_fields = [field for field in news_required_fields if not incident_id and field not in incident_data]
        if missing_news_fields:
            raise ValueError(f"Missing required fields for new 'news' incident: {', '.join(missing_news_fields)}")

    is_update = incident_id is not None

    if is_update:
        incident = Incident.collection.get(f"incident/{incident_id}")
        if not incident:
            raise ValueError(f"Incident with id {incident_id} not found.")
    else: # Create
        incident = Incident()
        # Set defaults for creation
        incident.type = incident_type
        if incident.type == "self_report":
            incident.self_report_status = "new"
        
    # Common required fields
    incident.incident_time = dateparser.parse(incident_data["incident_time"]) if isinstance(incident_data["incident_time"], str) else incident_data["incident_time"]
    incident.incident_location = incident_data["incident_location"]
    incident.abstract = incident_data["abstract"]

    # Common optional fields
    if 'abstract_translate' in incident_data:
        incident.abstract_translate = incident_data["abstract_translate"]
    if 'publish_status' in incident_data:
        incident.publish_status = incident_data["publish_status"]
    if 'donation_link' in incident_data:
        incident.donation_link = incident_data["donation_link"]
    if 'police_tip_line' in incident_data:
        incident.police_tip_line = incident_data["police_tip_line"]
    if 'help_the_victim' in incident_data:
        incident.help_the_victim = incident_data["help_the_victim"]

    # News-specific fields
    if incident_type == 'news':
        incident.url = incident_data.get("url")
        incident.incident_source = incident_data.get("incident_source")
        incident.created_by = incident_data.get("created_by")
        incident.title = incident_data.get("title")
        incident.title_translate = incident_data.get("title_translate")

    # Self-report-specific fields
    if 'attachments' in incident_data:
        incident.attachments = incident_data["attachments"]
    if 'self_report_status' in incident_data:
        if incident_data["self_report_status"] not in VALID_SELF_REPORT_STATUSES:
            raise ValueError(f"Invalid self_report_status: {incident_data['self_report_status']}")
        incident.self_report_status = incident_data["self_report_status"]
    if 'approved_by' in incident_data:
        incident.approved_by = incident_data["approved_by"]
    if 'contact_name' in incident_data:
        incident.contact_name = incident_data["contact_name"]
    if 'email' in incident_data:
        incident.email = incident_data["email"]
    if 'phone' in incident_data:
        incident.phone = incident_data["phone"]


    result_id = incident.upsert().id

    if result_id:
        if to_flush_cache:
            flush_cache()
        return result_id
    else:
        raise SystemError(f"Failed to upsert incident.")


# Query incidents within the given dates and state
# Return [ { key: date, value : count, incident_location: state } ]


@cached(cache=INCIDENT_STATS_CACHE)
def getStats(start: datetime, end: datetime, state="", type="", self_report_status=""):
    stats = {}  # (date, state) : {"news": count, "self_report": count}
    # getStats needs to get all incidents at once, so it needs to pagimate through
    # all results using cursors until all incidents are fetched
    current_cursor = None
    has_next = True
    all_incidents = []
    while has_next:
        # The page size setting are open to discussion
        result = queryIncidents(start, end, state, type, self_report_status, 1200, current_cursor)
        # Check if we got an error response
        if isinstance(result, dict) and "error" in result:
            return []
        # Extract incidents from the response
        incidents = result["incidents"]
        all_incidents.extend(incidents)
        has_next = result["pagination"]["has_next"]
        if has_next:
            next_cursor = result["pagination"]["next_cursor"]["id"]
            current_cursor = {
                'id': next_cursor
            }

    for incident in all_incidents:
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

def update_user_report_contact(incident_id: str, contact_data: dict):
    """
    Updates the contact information (name, email, phone) for a specific self-report incident.
    
    Args:
        incident_id (str): The ID of the incident to update.
        contact_data (dict): A dictionary containing the contact fields to update.
    
    Returns:
        str: The ID of the updated incident.
        
    Raises:
        ValueError: If the incident is not found or is not a 'self-report'.
    """
    incident = Incident.collection.get(f"incident/{incident_id}")

    if not incident:
        raise ValueError(f"Incident with id {incident_id} not found.")

    if incident.type != 'self_report':
        raise ValueError("Contact information can only be updated for self-report incidents.")

    incident.contact_name = contact_data.get("contact_name", incident.contact_name)
    incident.email = contact_data.get("email", incident.email)
    incident.phone = contact_data.get("phone", incident.phone)
    
    incident.update()
    flush_cache()
    return incident.id

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
