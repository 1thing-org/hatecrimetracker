from datetime import datetime
from fireo import models as mdl

class IncidentPublishStatus(mdl.Model):
    incident_id = mdl.TextField(required=True)
    updated_on = mdl.DateTime(auto=True)
    publish_status = mdl.MapField(required=True)

def getIncidentPublishStatus(incident_id) -> IncidentPublishStatus:    
    ret = IncidentPublishStatus.collection.filter(
        'incident_id', '=', incident_id).get()        
    if ret:
        return ret.to_dict()
    else:
        return IncidentPublishStatus(
            incident_id=incident_id,
            publish_status = {}
        )

def upsertIncidentPublishStatus(incident_update_status: dict):
    new_incident_publish_status = IncidentPublishStatus(
        incident_id=incident_update_status["incident_id"],
        updated_on = datetime.now(),
        publish_status = incident_update_status.publish_status
        )
    new_incident_publish_status.id = incident_update_status["id"] if "id" in incident_update_status else None
    id = new_incident_publish_status.upsert().id
    if id:
        return id
    else:
        raise SystemError("Failed to upsert the incident publish status with id:" + incident_update_status.id)
