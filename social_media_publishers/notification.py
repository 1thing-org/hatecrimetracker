from datetime import datetime
from social_media_publishers.publisher import Publisher
from firestore.incidents import Incident
from firestore.tokens import Token, delete_token

from exponent_server_sdk import (
    DeviceNotRegisteredError,
    PushClient,
    PushMessage,
    PushServerError,
)


# Expo rejects batches that mix tokens from different Expo projects
# (experience IDs) with this error code. The error payload includes a
# `details` map of {experience_id: [tokens]} we can use to split the
# batch and retry one experience at a time.
EXPO_MIXED_EXPERIENCE_ERROR = "PUSH_TOO_MANY_EXPERIENCE_IDS"


class PushNotification(Publisher):
    def __init__(self) -> None:
        self.push_client = PushClient()

    def publish(self, incident: Incident) -> datetime:
        # Only notify devices that were registered before this incident
        # was added to the system. We compare against `created_on` (not
        # `incident_time`) so back-dated incidents added after a user
        # registers still reach them.
        batch_size = 1000
        batch_no = 0
        tokens = (
            Token.collection
            .filter("registered_at", "<=", incident.created_on)
            .fetch(batch_size)
        )
        res = []

        while True:
            batch_no += 1

            print(f"Grouping batch {batch_no} ...")
            # Keep a token->Token-doc map so we can delete invalid ones
            # by id later if Expo tells us to.
            token_index = {}
            push_messages = []
            for token in tokens:
                token_index[token.token] = token
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

            print(f"Publishing batch {batch_no} ({len(push_messages)} messages) ...")
            self._send_with_experience_split(push_messages, token_index, res)
            tokens.next_fetch()

        return datetime.now()

    def _send_with_experience_split(self, push_messages, token_index, results_out):
        """Send `push_messages` with `publish_multiple`; if Expo rejects
        the request because it contains multiple experience IDs, split
        by experience and retry each group.
        """
        try:
            results_out.append(self.push_client.publish_multiple(push_messages))
        except DeviceNotRegisteredError:
            # The SDK only raises this when receipts come back per-token;
            # for a mixed batch it bubbles up as PushServerError. We keep
            # this here for the per-experience retry path below.
            print("Token Not Registered in batch (unspecified).")
        except PushServerError as error:
            mixed = self._extract_experience_buckets(error)
            if mixed is None:
                print("Push failed: ", error.__dict__)
                return

            print(
                f"Expo rejected mixed-experience batch; splitting into "
                f"{len(mixed)} groups and retrying."
            )
            for experience_id, token_strs in mixed.items():
                sub_messages = [
                    pm for pm in push_messages if pm.to in set(token_strs)
                ]
                if not sub_messages:
                    continue
                print(
                    f"  -> retrying {len(sub_messages)} messages for "
                    f"experience {experience_id}"
                )
                try:
                    results_out.append(
                        self.push_client.publish_multiple(sub_messages)
                    )
                except PushServerError as sub_error:
                    # If a per-experience send still fails, the tokens for
                    # that experience are unusable from this server (e.g.
                    # we have no push credentials for that project). Drop
                    # them so they stop poisoning future batches.
                    print(
                        f"     experience {experience_id} still failed: "
                        f"{sub_error.__dict__}. Deleting its tokens."
                    )
                    for tok_str in token_strs:
                        tok_doc = token_index.get(tok_str)
                        if tok_doc is not None:
                            delete_token(tok_doc._id)
                except DeviceNotRegisteredError:
                    print(
                        f"     experience {experience_id} reported "
                        f"DeviceNotRegistered; deleting affected tokens."
                    )
                    for tok_str in token_strs:
                        tok_doc = token_index.get(tok_str)
                        if tok_doc is not None:
                            delete_token(tok_doc._id)
                except ValueError:
                    print(
                        f"     experience {experience_id} had an invalid "
                        f"token; deleting its tokens."
                    )
                    for tok_str in token_strs:
                        tok_doc = token_index.get(tok_str)
                        if tok_doc is not None:
                            delete_token(tok_doc._id)
        except ValueError:
            # Whole batch had at least one malformed token; can't tell
            # which one from here, so just log and move on. The
            # per-experience path above handles the targeted case.
            print("Invalid push token in batch.")

    @staticmethod
    def _extract_experience_buckets(error):
        """If `error` is the Expo PUSH_TOO_MANY_EXPERIENCE_IDS error,
        return the {experience_id: [tokens]} map from its details.
        Otherwise return None.
        """
        response_data = getattr(error, "response_data", None) or {}
        errors = response_data.get("errors") or []
        for err in errors:
            if err.get("code") == EXPO_MIXED_EXPERIENCE_ERROR:
                details = err.get("details") or {}
                if isinstance(details, dict) and details:
                    return details
        return None
