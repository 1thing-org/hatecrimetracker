from fireo.models import Model
from fireo.fields import IDField, TextField, DateTime
from datetime import datetime


class Token(Model):
    id = IDField(required=True)
    token = TextField(required=True)
    # When this device first registered. Used by the notification publisher
    # to skip incidents that happened before the user opted in, so new
    # users are not flooded with old incidents.
    registered_at = DateTime()


def delete_token(token_id):
    return Token.collection.delete("token/" + token_id)


def add_token(deviceID, token):
    print("New Device:", deviceID)
    print("New Token:", token)

    existing = Token.collection.get("token/" + deviceID)
    registered_at = existing.registered_at if existing and existing.registered_at else datetime.utcnow()

    new_token = Token(
        id=deviceID,
        token=token,
        registered_at=registered_at,
    )

    token_id = new_token.upsert().id
    if token_id:
        return token_id
    else:
        raise SystemError("Failed to upsert the incident with id:" + token_id)
