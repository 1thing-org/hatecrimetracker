from datetime import datetime
from requests_oauthlib import OAuth1Session
from social_media_publishers.publisher import Publisher
from firestore.incidents import Incident
from google.cloud import secretmanager 
import json
from datetime import datetime

# test account at https://twitter.com/OTTest11
# Sample code: https://github.com/twitterdev/Twitter-API-v2-sample-code/blob/main/Manage-Tweets/create_tweet.py
_TWITTER_TEMPLATE = "{incident_location} - {incident_time}: {title}\n{url} #1thingagainstracism"

'''
Twitter secrete id looks like this:
    projects/46658644173/secrets/1thing_twitter_credential

Twitter Secret data looks like this:
{
"api_key": "xxxxxxx",
"api_key_secret": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
"access_token": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
"access_token_secret": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"",
"bearer_token": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}


'''
class TwitterV2(Publisher):
    def __init__(self):
        self.__client = secretmanager.SecretManagerServiceClient()
        secrete_version = "projects/46658644173/secrets/1thing_twitter_credential/versions/latest"
        response = self.__client.access_secret_version(request={"name": secrete_version})
        credential = json.loads(response.payload.data.decode("UTF-8"))

        # Make the request
        self._oauth = OAuth1Session(
            # consumer_key=
            credential["api_key"],
            client_secret=credential["api_key_secret"],
            resource_owner_key=credential["access_token"],
            resource_owner_secret=credential["access_token_secret"],
        )
    
    def publish(self, incident: Incident) -> datetime:
        print("Publish incident to twitter: ", incident.id, ":", incident.title)
        payload = {"text": _TWITTER_TEMPLATE.format(
            incident_time = incident.incident_time.strftime("%m/%d/%Y"),
            title = incident.title,
            abstract = incident.abstract, incident_location = incident.incident_location, 
            url = "https://hatecrimetracker.1thing.org" #incident.url
            )}
        # Making the request
        response = self._oauth.post(
            "https://api.twitter.com/2/tweets",
            json=payload,
        )

        # Saving the response as JSON
        json_response = response.json()
        print("json_response:", json.dumps(json_response, indent=4, sort_keys=True))

        if response.status_code != 201:
            # raise Exception(
            #     "Request returned an error: {} {}".format(response.status_code, response.text)
            # )
            return

        print("Response code: {}".format(response.status_code))

        # Saving the response as JSON
        json_response = response.json()
        print(json.dumps(json_response, indent=4, sort_keys=True))


        # status = self.__api.PostUpdate(_TWITTER_TEMPLATE.format(incident_time = incident.incident_time,
        #     subject = incident.subject,
        #     abstract = incident.abstract, incident_location = incident.incident_location, url = incident.url))
        # if status.id is None:
        #     # do we have id for an incident?
        #     print("Publishing to twitter failed for incident: " + incident.id + ":" + incident.subject)
        return datetime.now()
