from fireo.models import Model
from fireo.fields import IDField, TextField, DateTime
from datetime import datetime, timedelta


class Token(Model):
    id = IDField(required=True)
    token = TextField(required=True)


def delete_token(token_id):
    return Token.collection.delete("token/" + token_id)


def add_token(deviceID, token):
    print("New Device:", deviceID)
    print("New Token:", token)
    new_token = Token(
        id=deviceID,
        token=token,
    )

    token_id = new_token.upsert().id
    if token_id:
        return token_id
    else:
        raise SystemError("Failed to upsert the incident with id:" + token_id)
