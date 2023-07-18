from fireo.models import Model
from fireo.fields import IDField, TextField, DateTime
from datetime import datetime, timedelta


class Token(Model):
    id = IDField(required=True)
    token = TextField(required=True)
    expiration_time = DateTime(required=True)


def deleteToken(token_id):
    if Token.collection.delete("token/" + token_id):
        return True
    return False


def registerNewToken(id, token):
    # return incident id
    print("New Id:", id)
    print("New Token:", token)
    new_token = Token(
        id=id,
        token=token,
        expiration_time=datetime.now() + timedelta(days=30),
    )

    token_id = new_token.upsert().id
    if token_id:
        return token_id
    else:
        raise SystemError("Failed to upsert the incident with id:" + token_id)
