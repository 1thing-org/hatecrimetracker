from datetime import datetime

import dateparser
from cachetools import cached
from fireo import models as mdl

from firestore.cachemanager import INCIDENT_CACHE, INCIDENT_STATS_CACHE, flush_cache


class UserReport(mdl.Model):
    user_report_time = mdl.DateTime(required=True)
    created_on = mdl.DateTime(auto=True)
    user_report_location = mdl.TextField(required=True)
    description = mdl.TextField(required=True)
    attachments = mdl.TextField(required=True)
    status = mdl.TextField(required=False) # set to False for the convenience of development, need to change to True in the future
    description_translate = mdl.MapField(required=False)
    approved_by = mdl.TextField(required=False)  # Contact info is not required
    email = mdl.TextField(required=False)
    phone = mdl.TextField(required=False)
    title = mdl.TextField(required=False)  # Title is not required for user reports
    title_translate = mdl.MapField(required=False)
    publish_status = mdl.MapField(
        required=True, default={"twitter": None, "linkedin": None, "notification": None}
    )
    donation_link = mdl.TextField()  #  Donation: link to donation website
    police_tip_line = (
        mdl.TextField()
    )  # Police Tip Line: phone number to provide tips to police to help capture the suspect
    help_the_victim = (
        mdl.TextField()
    )  # Help the victim: other free style text about how people can help the victim


def insertUserReport(user_report, to_flush_cache=True):
    # return user_report id
    print("INSERTING:", user_report)
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
    new_user_report.title = user_report["title"] if "title" in user_report else None
    new_user_report.title_translate = (
        user_report["title_translate"] if "title_translate" in user_report else {}
    )
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
