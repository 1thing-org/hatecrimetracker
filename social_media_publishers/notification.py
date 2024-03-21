from datetime import datetime
from social_media_publishers.publisher import Publisher
from firestore.incidents import Incident
from firestore.tokens import Token, delete_token
from datetime import datetime
import concurrent.futures

from exponent_server_sdk import (
    DeviceNotRegisteredError,
    PushClient,
    PushMessage,
    PushServerError,
)


class PushNotification(Publisher):
    def __init__(self) -> None:
        self.push_client = PushClient()

    def publish(self, incident: Incident) -> datetime:
        # Fetch tokens in batches
        batch_size = 1000
        batch_no = 0
        tokens = Token.collection.fetch(batch_size)
        res = []

        while True:
            batch_no += 1

            print(f"Grouping batch {batch_no} ...")
            push_messages = []
            for token in tokens:
                push_messages.append(
                    PushMessage(
                        to=token.token,
                        title=incident.title,
                        body=incident.abstract,
                        data={},  # Optional data payload
                    )
                )
            if not push_messages:
                break

            print(f"Publishing batch {batch_no} ...")
            try:
                results = self.push_client.publish_multiple(push_messages)
                res.append(results)
            except DeviceNotRegisteredError:
                delete_token(token._id)
                print("Token Not Registered. Deleted.")
            except PushServerError as error:
                print("Push failed: ", error.__dict__)
            except ValueError:
                delete_token(token._id)
                print(f"Invalid push token. Deleted.")
            tokens.next_fetch()

        return datetime.now()
