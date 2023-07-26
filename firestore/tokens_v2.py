from fireo.models import Model
from fireo.fields import IDField, MapField
import hashlib


class Token(Model):
    id = IDField(required=True)
    tokens = MapField(required=True)


def shard_hash(deviceID):
    return str(int(hashlib.sha1(deviceID.encode("utf-8")).hexdigest(), 16) % 1000)


def add_token(deviceID, token):
    shard_id = shard_hash(deviceID)
    shard_doc = Token.collection.get(f"token/{shard_id}")

    if not shard_doc:
        shard_doc = Token(id=shard_id, tokens={deviceID: token})
        shard_doc.save()
        print("new token added")
        return

    tokens = shard_doc.tokens
    if deviceID in tokens and token == tokens[deviceID]:
        print("same token, no need to update")
        return

    # if token is to be updated, or new deviceID registered
    tokens[deviceID] = token
    shard_doc.tokens = tokens
    shard_doc.update()
    print("token updated")


def delete_token(deviceID):
    shard_id = shard_hash(deviceID)
    shard_doc = Token.collection.get(f"token/{shard_id}")

    if not shard_doc:
        return "token not exist"

    tokens = shard_doc.tokens
    if deviceID not in tokens:
        return "token not exist"

    tokens.pop(deviceID)
    if not tokens:
        Token.collection.delete(shard_id)
    else:
        shard_doc.tokens = tokens
        shard_doc.update()
    return "token deleted"
