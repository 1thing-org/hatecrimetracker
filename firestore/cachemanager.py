from datetime import datetime
import firebase_admin
from cachetools import TTLCache, cached
from firebase_admin import db

ADMIN_CACHE = TTLCache(maxsize=128, ttl=3600 * 24)
INCIDENT_CACHE = TTLCache(maxsize=1024, ttl=3600 * 24)
INCIDENT_STATS_CACHE = TTLCache(maxsize=1024, ttl=3600 * 24)

last_cache_update_date = ""


def __clear_cache():
    ADMIN_CACHE.clear()
    INCIDENT_CACHE.clear()
    INCIDENT_STATS_CACHE.clear()


def __listener(event):
    global last_cache_update_date
    if event.data == last_cache_update_date:
        print("Cache update data not changed. Skip.")
        return
    last_cache_update_date = event.data
    __clear_cache()
    # can be 'put' or 'patch'
    print("cache_update event type:", event.event_type)
    # relative to the reference, it seems
    print("cache_update event path:", event.path)
    # new data at /reference/event.path. None if deleted
    print("cache_update event data:", event.data)


# Make sure to create a realtime db with the following URL and a json path called as /cache_update
my_app_name = "tracker"
options = {
    "databaseURL": "https://hate-crime-tracker-dev-default-rtdb.firebaseio.com/",
    "storageBucket": "hate-crime-tracker.appspot.com",
}
filebase_app = firebase_admin.initialize_app(options=options, name=my_app_name)
cache_update_db_ref = db.reference("/cache_update", app=filebase_app)
cache_update_db_ref.listen(__listener)


def flush_cache():
    __clear_cache()
    cache_update_db_ref.set(datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
