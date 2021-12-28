from firestore.incidents import Incident
from datetime import datetime
class Publisher:
    # return None if the publish action failed
    def publish(self, incident: Incident) -> datetime:
        return None
