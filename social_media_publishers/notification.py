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
        batch_size = 100
        batch_no = 0
        tokens = Token.collection.fetch(batch_size)

        while True:
            batch_no += 1
            print(f"Grouping batch {batch_no} ...")

            # Group tokens by first two characters
            grouped_tokens = {}
            for token in tokens:
                group_key = token.token[18:20]
                # example token: ExponentPushToken[hty9r4BGScZt5gloxXCITM]
                if group_key not in grouped_tokens:
                    grouped_tokens[group_key] = []
                grouped_tokens[group_key].append(token)

            if not grouped_tokens:
                break

            # Process each group in parallel
            with concurrent.futures.ThreadPoolExecutor() as executor:
                print(f"Sending to batch {batch_no} ...")
                futures = []
                for group_key, group_tokens in grouped_tokens.items():
                    future = executor.submit(
                        self.process_token_group, group_key, group_tokens, incident
                    )
                    futures.append(future)

                # Wait for all tasks to complete
                concurrent.futures.wait(futures)

            tokens.next_fetch()

        return datetime.now()

    def process_token_group(self, group_key, tokens, incident):
        try:
            for token in tokens:
                message = PushMessage(
                    to=token.token,
                    title=incident.title,
                    body=incident.abstract,
                    data={},  # Optional data payload
                )
                self.sendMessage(message, token)
        except Exception as e:
            print(e)

    def sendMessage(self, message, token):
        try:
            response = self.push_client.publish(message)
            print("Notification sent successfully:", response)
        except DeviceNotRegisteredError:
            delete_token(token._id)
            print("Token Not Registered. Deleted.")
        except PushServerError as error:
            print("Push failed: ", error.__dict__)
        except ValueError:
            delete_token(token._id)
            print(f"Invalid push token. Deleted.")
