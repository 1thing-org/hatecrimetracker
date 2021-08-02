from datetime import datetime
import firebase_admin
from cachetools import TTLCache, cached
from firebase_admin import db

ADMIN_CACHE = TTLCache(maxsize=128, ttl=3600*24)
INCIDENT_CACHE = TTLCache(maxsize=1024, ttl=3600*24)
INCIDENT_STATS_CACHE = TTLCache(maxsize=1024, ttl=3600*24)

def __clear_cache():
    ADMIN_CACHE.clear()
    INCIDENT_CACHE.clear()
    INCIDENT_STATS_CACHE.clear()
def __listener(event):
    __clear_cache()
    print("cache_update event type:", event.event_type)  # can be 'put' or 'patch'
    print("cache_update event path:", event.path)  # relative to the reference, it seems
    print("cache_update event data:", event.data)  # new data at /reference/event.path. None if deleted


# Make sure to create a realtime db with the following URL and a json path called as /cache_update
my_app_name = 'hate-crime-tracker'
options = {'databaseURL': 'https://hate-crime-tracker-default-rtdb.firebaseio.com',
           'storageBucket': 'hate-crime-tracker.appspot.com'}
filebase_app = firebase_admin.initialize_app(options=options, name=my_app_name)
cache_update_db_ref = db.reference('/cache_update', app=filebase_app)
cache_update_db_ref.listen(__listener)

def flush_cache():
    __clear_cache
    cache_update_db_ref.set(datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
