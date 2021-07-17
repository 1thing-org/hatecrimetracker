from fireo import models as mdl

class Admin(mdl.Model):
    email = mdl.TextField()

# TODO cache
def get_admins() : 
    return Admin.collection.fetch()

def is_admin(email) -> bool:
    for admin in get_admins():
        if admin.email==email:
            return True
    return False