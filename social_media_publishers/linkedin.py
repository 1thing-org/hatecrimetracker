from datetime import datetime
from social_media_publishers.publisher import Publisher
from firestore.incidents import Incident
import requests
from google.cloud import secretmanager 
from social_media_publishers.ln_oauth import auth, headers
import json

_LINKEDIN_TEMPLATE = "{incident_location} - {incident_time} : {title}\n{abstract}\nSource: {url}#stopaapihate #stopasianhate"
_API_URL = 'https://api.linkedin.com/v2/ugcPosts'
class LinkedIn(Publisher):
    def __init__(self):
        
        self.__client = secretmanager.SecretManagerServiceClient()
        secrete_version = "projects/46658644173/secrets/1thing_linkedin_credential/versions/latest"

        response = self.__client.access_secret_version(request={"name": secrete_version})
        print("secrete response:", response)

        credential = json.loads(response.payload.data.decode("UTF-8"))
        print ("credential:", credential)
        access_token = auth(credential) # Authenticate the API
        self.__headers = headers(access_token) # Make the headers to attach to the API call.

        # author = f'urn:li:person:{urn}'
        self.__author = "urn:li:organization:78324103" # 2278324103"



    def publish(self, incident: Incident) -> datetime:
        
        print("Publish incident to linkedin: ", incident.id, ":", incident.title)
        message = _LINKEDIN_TEMPLATE.format(
            incident_time = incident.incident_time.strftime("%m/%d/%Y"),
            title = incident.title,
            abstract = incident.abstract, incident_location = incident.incident_location, 
            url = incident.url
            )

        link = 'https://hatecrimetracker.1thing.org/'
        link_text = 'Anti-Asian Hate Crime Tracker'
        link_message = "Check more anti-Asian hate incidents at the Hate Crime Tracker."
        
        post_data = {
            "author": self.__author,
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {
                            "text": message
                        },
                        "shareMediaCategory": "ARTICLE",
                        "media": [
                            {
                                "status": "READY",
                                "description": {
                                    "text": link_message
                                },
                                "originalUrl": link,
                                "title": {
                                    "text": link_text
                                }
                            }
                        ]
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                }
            }
        requests.post(_API_URL, headers=self.__headers, json=post_data)
        return datetime.now()