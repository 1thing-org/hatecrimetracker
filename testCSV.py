from firestore.incidents import Incident
from cachetools import cached
from firestore.cachemanager import (INCIDENT_CACHE, INCIDENT_STATS_CACHE,
                                    flush_cache)
import csv


@cached(cache=INCIDENT_CACHE)
def get_all_incidents():
    res = []
    for incident in Incident.collection.fetch():
        res.append(incident.to_dict())
    return res


def to_csv():
    cols = ["incident_time", "incident_location", "abstract",  "created_on", "url", "incident_source", "title"]
    with open("incident_data.csv", 'w', encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=cols, extrasaction='ignore')
        writer.writeheader()
        for incident in get_all_incidents():
            writer.writerow(incident)

to_csv()
