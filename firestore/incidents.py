from datetime import datetime

import dateparser
from cachetools import cached
from fireo import models as mdl

from firestore.cachemanager import INCIDENT_CACHE, INCIDENT_STATS_CACHE, flush_cache
from firestore.get_all_validation import get_all_validation


class Incident(mdl.Model):
    incident_time = mdl.DateTime(required=True)
    created_on = mdl.DateTime(auto=True)
    incident_location = mdl.TextField()
    abstract = mdl.TextField(required=True)
    abstract_translate = mdl.MapField(required=False)
    url = mdl.TextField(required=False)
    incident_source = mdl.TextField(required=True)
    created_by = mdl.TextField(required=False)
    title = mdl.TextField(required=True)
    title_translate = mdl.MapField(required=False)
    publish_status = mdl.MapField(
        required=True, default={"twitter": None, "linkedin": None}
    )
    donation_link = mdl.TextField()  #  Donation: link to donation website
    police_tip_line = (
        mdl.TextField()
    )  # Police Tip Line: phone number to provide tips to police to help capture the suspect
    help_the_victim = (
        mdl.TextField()
    )  # Help the victim: other free style text about how people can help the victim
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


# incidents should be [
#   {
#       "id" : id, //optional
#       "incident_time" : incident_time
#       "created_on"    : created_on
#       "incident_location": incident_location
#       "abstract"  : abstract
#       "abstract_translate": abstract_translate
#       "url"           : url
#       "incident_source": incident_source
#       "created_by" : created_by
#       "title"         : title
#       "title_translate" : title_translate
#       "publish_status" : publish_status
#       "donation_link" : donation_link
#       "police_tip_line" : police_tip_line
#       "help_the_victim" : help_the_victim
#   }
# ]


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
    
    # Extract parameters with defaults
    incident_status = params.get('status', 'both')
    self_report_status = params.get('self_report_status', 'approved' if user_role == 'viewer' else 'new')
    state = params.get('state', '')
    start_date = dateparser.parse(params.get('start_date', '2021-09-08')) # Default start date, the earliest incident i found in firebase
    end_date = dateparser.parse(params.get('end_date', datetime.now().strftime("%Y-%m-%d")))
    page_size = int(params.get('page_size', 10))
    start_row = int(params.get('start_row', 0))

    # Construct the base query
    query = Incident.collection.filter("incident_time", ">=", start_date).filter(
        "incident_time", "<=", end_date
    )

    # Apply state filter if provided
    if state:
        query = query.filter("incident_location", "==", state)

    # Apply filters based on the status of the incident
    if incident_status != 'both':
        query = query.filter("incident_source", "==", incident_status)

    # Apply filters based on self-report status for the 'self-report' type only
    if incident_status == 'self-report' and self_report_status != 'all':
        query = query.filter("publish_status.self_report_status", "==", self_report_status)

    # Enforce admin rule: self_report_status should only be used when type is 'self-report'
    if user_role == 'admin' and self_report_status != 'new' and incident_status != 'self-report':
        return {"error": "Invalid query. 'self_report_status' can only be used when 'type' is set to 'self-report'."}, 400

    # Sort the results by the incident time in descending order
    query = query.order("-incident_time")

    # Handle pagination using start_row
    incidents = query.fetch(offset=start_row, limit=page_size)
    incidents_list = [incident.to_dict() for incident in incidents]

    # Prepare the response, no need for total and next page token for now
    response = {
        "page_info": {
            "start_row": 0,
            "page_size": 10,
        },
        "incidents": incidents_list
    }
    return response, 200