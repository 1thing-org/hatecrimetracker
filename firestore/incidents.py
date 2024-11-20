from datetime import datetime

import dateparser
from cachetools import cached
from fireo import models as mdl

from firestore.cachemanager import INCIDENT_CACHE, INCIDENT_STATS_CACHE, flush_cache


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
    email = mdl.TextField(required=False)
    phone = mdl.TextField(required=False)


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


# class Incident(mdl.Model):
#     incident_time = mdl.DateTime(required=True)
#     created_on = mdl.DateTime(auto=True)
#     incident_location = mdl.TextField()
#     abstract = mdl.TextField(required=True)
#     abstract_translate = mdl.MapField(required=False)
#     url = mdl.TextField(required=False)
#     incident_source = mdl.TextField(required=False)
#     created_by = mdl.TextField(required=False)
#     title = mdl.TextField(required=False)
#     title_translate = mdl.MapField(required=False)
#     publish_status = mdl.MapField(
#         required=True, default={"twitter": None, "linkedin": None, "notification": None}
#     )
#     donation_link = mdl.TextField()  #  Donation: link to donation website
#     police_tip_line = (
#         mdl.TextField()
#     )  # Police Tip Line: phone number to provide tips to police to help capture the suspect
#     help_the_victim = (
#         mdl.TextField()
#     )  # Help the victim: other free style text about how people can help the victim
#     parent_doc = mdl.TextField(column_name="parent")


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
        user_report["status"] if "status" in user_report else {}
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