from datetime import datetime
from social_media_publishers.linkedin import LinkedIn
from social_media_publishers.twitter_v2 import TwitterV2
from social_media_publishers.notification import PushNotification
from firestore.incidents import Incident
from dotenv import load_dotenv
import os

load_dotenv()
FLASK_ENV = os.getenv("FLASK_ENV")

# check all incidents in database, and publish those have not yet been published yet
# update incident.publish_status when done


def publish_incidents():
    success = 0
    failed = 0
    if FLASK_ENV == "development":
        PUBLISHERS = {
            "notification": PushNotification(),
        }
        incidents = (
            Incident.collection.filter("incident_time", ">=", datetime(2024, 1, 1))
            .order("incident_time")
            .fetch()
        )
    else:
        PUBLISHERS = {
            "twitter": TwitterV2(),
            "linkedin": LinkedIn(),
            "notification": PushNotification(),
        }
        incidents = (
            Incident.collection.filter("incident_time", ">=", datetime(2022, 1, 22))
            .order("incident_time")
            .fetch()
        )

    for incident in incidents:
        for target, publisher in PUBLISHERS.items():
            if not incident.publish_status:
                incident.publish_status = {}
            if target in incident.publish_status and incident.publish_status[target]:
                continue  # already published to the target
            print(
                "Publishing incident to {} using publisher {}".format(target, publisher)
            )
            publish_time = publisher.publish(incident)
            if not publish_time:
                print("Failed to publish to ", target)
                failed += 1
                continue
            print("Successfully published to ", target, " at ", publish_time)
            incident.publish_status[target] = publish_time
            # Uncomment me once the publishers are working
            try:
                incident.save()
                print("Successfully saved publish_status: " + incident.to_dict()["id"])
            except Exception as e:
                print(
                    "An error occurred:",
                    e,
                    incident.to_dict()["id"],
                )
            success += 1
    print("success:", success, " failed:", failed)
