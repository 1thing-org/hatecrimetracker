from social_media_publishers.linkedin import LinkedIn
from social_media_publishers.twitter import Twitter
from firestore.incidents import Incident

# check all incidents in database, and publish those have not yet been published yet
# update incident.publish_status when done

def publish_incidents():
    success = 0
    failed = 0
    PUBLISHERS = {
        'twitter': Twitter(),
        'linkedin': LinkedIn()
    }
    for incident in Incident.collection.order('-incident_time').fetch():
        for target, publisher in PUBLISHERS.items():
            if not incident.publish_status:
                incident.publish_status = {}
            if target in incident.publish_status and incident.publish_status[target]:
                continue  # already published to the target
            publish_time = publisher.publish(incident)
            if not publish_time:
                print("Failed to publish to ", target)
                failed += 1
                continue
            print("Successfully published to ", target, " at ", publish_time)
            incident.publish_status[target] = publish_time
            # Uncomment me once the publishers are working
            # incident.save()
            success += 1
    print ("success:",success, " failed:", failed)