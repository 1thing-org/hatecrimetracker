from datetime import datetime
from social_media_publishers.publisher import Publisher
from firestore.incidents import Incident
import twitter

# test account at https://twitter.com/OTTest11

_TWITTER_TEMPLATE = "On {incident_time}, {abstract} at {incident_location}. + {url}"


class Twitter(Publisher):
    def publish(self, incident: Incident) -> datetime:
        api = twitter.Api(consumer_key=_TWITTER_API_KEY,
                      consumer_secret=_TWITTER_API_KEY_SECRET,
                      access_token_key=_TWITTER_ACCESS_TOKEN,
                      access_token_secret=_TWITTER_TOKEN_SECRET)
        print(api.VerifyCredentials())
        print("Publish incident to twitter: ", incident.to_dict())
        for incident in incidents:
            status = api.PostUpdate(_TWIITER_TEMPLATE.format(incident_time = incident.incident_time,
            abstract = incident.abstract, incident_location = incident.incident_location, url = incident.url))
            if status.id is None:
                # do we have id for an incident?
                print("Publishing to twitter failed for incident: " + incident.title)
        return datetime.now()
