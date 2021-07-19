from firestore.cachemanager import ADMIN_CACHE
import cachetools
from fireo import models as mdl

class Admin(mdl.Model):
    email = mdl.TextField()

@cachetools(cache=ADMIN_CACHE)
def get_admins() : 
    return Admin.collection.fetch()

def is_admin(email) -> bool:
    for admin in get_admins():
        if admin.email==email:
            return True
    return False