from datetime import datetime
from social_media_publishers.publisher import Publisher
from firestore.incidents import Incident


class Twitter(Publisher):
    def publish(self, incident: Incident) -> datetime:
        print("Publish incident to twitter: ", incident.to_dict())
        return datetime.now()
