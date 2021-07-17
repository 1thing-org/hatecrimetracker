from fireo import models as mdl

class Incident(mdl.Model):
    incident_time = mdl.DateTime(required=True)
    created_on = mdl.DateTime(auto=True)
    incident_location = mdl.TextField()
    abstract = mdl.TextField(required=True)
    url = mdl.TextField(required=False)
    incident_source = mdl.TextField(required=True)
    title = mdl.TextField(required=True)

def queryIncidents(start, end, state=""):
    query = Incident.collection.filter('incident_time', '>=', start).filter('incident_time', '<=', end)
    if state != "":
        query = query.filter('incident_location', '=', state)

    return query.order('-incident_time').fetch()

def getIncidents(start, end, state=""):
    result = queryIncidents(start, end, state)
    return [incident.to_dict() for incident in result]

# incidents should be [
#   {
#       "incident_time" : incident_time
#       "created_on"    : created_on
#       "incident_location": incident_location
#       "abstract"  : abstract
#       "url"           : url
#       "incident_source": incident_source
#       "title"         : title
#   }
# ]
def insertIncident(incident):
    print ("INSERTING:", incident)
    new_incident = Incident(incident_time=incident["incident_time"], incident_location=incident["incident_location"], 
        created_on=incident["created_on"], abstract=incident["abstract"], url=incident["url"], 
        incident_source=incident["incident_source"], title=incident["title"])
    new_incident.upsert()

# Query incidents within the given dates and state
# Return [ { key: date, value : count, incident_location: state } ]
def getStats(start, end, state = ""):
    stats = {} # (date, state) : count
    for incident in queryIncidents(start, end, state):
        incident_date = incident.incident_time.strftime("%Y-%m-%d")
        key = (incident_date, incident.incident_location)
        if key not in stats:
            stats[key] = 0
        stats[key] += 1

    ret = []
    for key in stats:
        (date, state) = key
        ret.append({
            "key" : date,
            "incident_location" : state,
            "value" : stats[key]
        })

    return ret        
