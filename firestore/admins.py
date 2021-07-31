from cachetools import cached
from firestore.cachemanager import ADMIN_CACHE
from fireo import models as mdl

class Admin(mdl.Model):
    email = mdl.TextField()

@cached(cache=ADMIN_CACHE)
def get_admins() : 
    ret = []
    for admin in Admin.collection.fetch():
        ret.append(admin)
    return ret

def is_admin(email) -> bool:
    for admin in get_admins():
        if admin.email==email:
            return True
    return False