from incidents import db

from sqlalchemy import text

QUERY_ALL_STATES=text("SELECT incident_location, key, count(id) AS value from "
    "(select incident_location, to_char(date_trunc(:datetime_resolution, incident_time),'YYYY-MM-DD') AS key, id FROM public.incidents "
        "WHERE incident_time >= :start AND incident_time <= :end) AS P GROUP BY key, incident_location ORDER BY key")

QUERY_ONE_STATE=text("SELECT key, count(id) AS value from "
    "(select to_char(date_trunc(:datetime_resolution, incident_time),'YYYY-MM-DD') AS key, id FROM public.incidents "
    "WHERE incident_time >= :start AND incident_time <= :end AND incident_location = :state) AS P GROUP BY key")

VALID_DATETIME_RESOLUTION = ("day", "month", "year")

def getStats(start, end, state = "", datetime_resolution = "day"):
    if datetime_resolution not in VALID_DATETIME_RESOLUTION:
        raise Exception("Invalid date time resolution")

    stats = []

    with db.connect() as conn:
        query = QUERY_ALL_STATES
        parameters = {"start": start, "end": end, "datetime_resolution": datetime_resolution}
        if state:
            query = QUERY_ONE_STATE
            parameters["state"] = state

        # Execute the query and fetch all results
        incidents = conn.execute(query, parameters)

        # Convert the results into a list of dicts representing stats
        for row in incidents:
            if state:
                stats.append({"key": row.key,  "value": row.value})
            else:
                stats.append({"key": row.key,  "incident_location": row.incident_location, "value": row.value})
    return stats
