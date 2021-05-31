from incidents import db

from sqlalchemy import text

def getStats(start, end):
    stats = []

    with db.connect() as conn:
        # Execute the query and fetch all results
        incidents = conn.execute(text(
            "SELECT to_char(date_trunc('month', incident_time),'YYYY-MM-DD') AS key, incident_location, COUNT(id) AS value FROM public.incidents "
            "WHERE incident_time >= :start AND incident_time <= :end "
            "GROUP BY incident_location, to_char(date_trunc('month', incident_time),'YYYY-MM-DD') "
            "ORDER BY incident_location"),
            {"start": start, "end": end})
        # Convert the results into a list of dicts representing votes
        for row in incidents:
            stats.append({"key": row.key,  "incident_location": row.incident_location, "value": row.value})
    return stats
