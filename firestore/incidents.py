from datetime import datetime

import dateparser
from cachetools import cached
from fireo import models as mdl

from firestore.cachemanager import (INCIDENT_CACHE, INCIDENT_STATS_CACHE,
                                    flush_cache)


class Incident(mdl.Model):
    incident_time = mdl.DateTime(required=True)
    created_on = mdl.DateTime(auto=True)
    incident_location = mdl.TextField()
    abstract = mdl.TextField(required=True)
    url = mdl.TextField(required=False)
    incident_source = mdl.TextField(required=True)
    created_by = mdl.TextField(required=False)
    title = mdl.TextField(required=True)


@cached(cache=INCIDENT_CACHE)
def queryIncidents(start, end, state=""):
    query = Incident.collection.filter(
        'incident_time', '>=', start).filter('incident_time', '<=', end)
    if state != "":
        query = query.filter('incident_location', '==', state)

    result = query.order('-incident_time').fetch()
    return [incident.to_dict() for incident in result]


def deleteIncident(incident_id):
    if Incident.collection.delete("incident/"+incident_id):
        flush_cache()
        return True
    return False


def getIncidents(start, end, state="", skip_cache=False):
    if skip_cache: 
        INCIDENT_CACHE.clear()
    return queryIncidents(start, end, state)

# incidents should be [
#   {
#       "incident_time" : incident_time
#       "created_on"    : created_on
#       "incident_location": incident_location
#       "abstract"  : abstract
#       "url"           : url
#       "incident_source": incident_source
#       "created_by" : created_by
#       "title"         : title
#   }
# ]


def insertIncident(incident):
    # return incident id
    print("INSERTING:", incident)
    new_incident = Incident(incident_time=dateparser.parse(incident["incident_time"]),
                            incident_location=incident["incident_location"],
                            abstract=incident["abstract"], url=incident["url"],
                            incident_source=incident["incident_source"], 
                            created_by=incident["created_by"],
                            title=incident["title"])
    id = new_incident.upsert().id
    if id:
        flush_cache()
        return id
    return None

# Query incidents within the given dates and state
# Return [ { key: date, value : count, incident_location: state } ]


@cached(cache=INCIDENT_STATS_CACHE)
def getStats(start, end, state=""):
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
        ret.append({
            "key": date,
            "incident_location": state,
            "value": stats[key]
        })

    return ret
