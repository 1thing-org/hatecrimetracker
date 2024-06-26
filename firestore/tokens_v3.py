from fireo.models import Model
from fireo.fields import NumberField, ListField
import fireo


class Token(Model):
    devices = ListField(required=True)
    tokens = ListField(required=True)
    avail = NumberField(required=True)


def add_token(deviceID, token):
    transaction = fireo.transaction(max_attempts=100)

    @fireo.transactional
    def add_token_transaction(transaction, deviceID, token):
        shard_doc = (
            Token.collection.filter("devices", "array_contains", deviceID)
            .transaction(transaction)
            .get()
        )
        if shard_doc:
            idx = shard_doc.devices.index(deviceID)
            tokens = shard_doc.tokens
            if tokens[idx] == token:
                print("same token, no need to update")
                return

            # update token
            tokens[idx] = token
            shard_doc.tokens = tokens
            shard_doc.update(transaction=transaction)
            print("token updated")
            return

        shard_doc = (
            Token.collection.filter("avail", ">", 0).transaction(transaction).get()
        )
        if shard_doc:
            shard_doc.devices = shard_doc.devices + [deviceID]
            shard_doc.tokens = shard_doc.tokens + [token]
            shard_doc.avail = shard_doc.avail - 1
            shard_doc.update(transaction=transaction)
        else:
            # create new doc
            shard_doc = Token(devices=[deviceID], tokens=[token], avail=999)
            shard_doc.save(transaction=transaction)
        print("new token added")

    add_token_transaction(transaction, deviceID, token)


# @fireo.transactional
# def delete_token(transaction, deviceID):
#     shard_doc = (
#         Token.collection.filter("devices", "array_contains", deviceID)
#         .transaction(transaction)
#         .get()
#     )
#     if not shard_doc:
#         print("token not exist")
#         return

#     devices = shard_doc.devices
#     tokens = shard_doc.tokens

#     idx = devices.index(deviceID)
#     lastIdx = len(devices) - 1
#     devices[idx], devices[lastIdx] = devices[lastIdx], devices[idx]
#     tokens[idx], tokens[lastIdx] = tokens[lastIdx], tokens[idx]
#     devices.pop()
#     tokens.pop()
#     shard_doc.devices = devices
#     shard_doc.tokens = tokens
#     shard_doc.update(transaction=transaction)
#     print("token deleted")
