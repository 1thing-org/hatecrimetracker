from fireo.models import Model
from fireo.fields import IDField, TextField


class Token(Model):
    id = IDField()
    token = TextField()


def deleteToken(token_id):
    if Token.collection.delete("token/" + token_id):
        return True
    return False


def saveNewToken(id, token):
    # return incident id
    print("New Id:", id)
    print("New Token:", token)
    new_token = Token()
    new_token.id = id
    new_token.token = token

    token_id = new_token.upsert().id
    if token_id:
        return token_id
    else:
        raise SystemError("Failed to upsert the incident with id:" + token_id)
