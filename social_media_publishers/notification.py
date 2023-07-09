from datetime import datetime
from social_media_publishers.publisher import Publisher
from firestore.incidents import Incident
from datetime import datetime
from firestore.tokens import Token

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
        # get all tokens
        tokens = Token.collection.fetch()
        print(tokens)

        # create message and send
        for token in tokens:
            message = PushMessage(
                to=token.token,
                title=incident.title,
                body=incident.abstract,
                data={},  # Optional data payload
            )
            self.send(message)
        return datetime.now()

    def send(self, message):
        try:
            response = self.push_client.publish(message)
            print("Notification sent successfully:", response)
        except DeviceNotRegisteredError:
            print("Device not registered.")
        except PushServerError as error:
            print("Push failed:", error.__dict__)
