
import csv
import datetime
from os import stat
from incidents import insertIncidents
from crawler.pygooglenews_util import GoogleNewsExtractor
import re
QUERY = 'anti-asian attack'
ALL_KEYWORDS =["asian", "crime"]
ANY_KEYWORDS = ["attack", "punch", "slur", "kill", "push", "stab", "hit", "spit", "curse", "slash", "beat", "smack", "assult", "rape", "knock"]

CITIES = {
    "New York": "NY",
    "Los Angeles": "CA",
    "Chicago": "IL",
    "Houston": "TX",
    "Philadelphia": "PA",
    "Phoenix": "AR",
    "San Antonio": "TX",
    "San Diego": "CA",
    "Dallas": "TX",
    "San Jose": "CA",
    "Austin": "TX",
    "Indianapolis": "IN",
    "Jacksonville": "FL",
    "San Francisco": "CA",
    "Columbus": "OH",
    "Charlotte": "NC",
    "Fort Worth": "TX",
    "Detroit": "MI",
    "El Paso": "TX",
    "Memphis": "TN",
    "Seattle": "WA",
    "Denver": "CO",
    "Washington": "DC",
    "Boston": "MA",
    "Nashville": "TN"
}


class NewsCrawler:

    def __init__(self, state="NY", city="New York"):
        self.TIME_DELTA = datetime.timedelta(1)
        self.state = state
        self.city = city
        self.incidentBuffer = []

    def __filter_by_id(self, id_str):
        """
        Return False iff |id_str| is duplicate. Otherwise return True and add it into the set.
        """
        if id_str in self.__id_set:
            return False
        else:
            self.__id_set.add(id_str)
            return True

    def filter_by_keywords(self, article):
        abstract = "{} {}".format(article[3], article[4]).lower()
        print ("Checking:"+abstract)
        if not all(keyword in abstract for keyword in ALL_KEYWORDS):
            return False
        if not any(keyword in abstract for keyword in ANY_KEYWORDS):
            return False
        if not self.city.lower() in abstract:
            return False
        print("Good!!!!!!!!")
        return True

    def extract_unique_key(self, article):
        pass

    # callback to be called by NewsExtractor
    def __handler(self, article):
        # [tmp_id, tmp_ts, tmp_publish_ts, tmp_title, tmp_abstract, tmp_location, tmp_url, tmp_source]
        if (not self.filter_by_keywords(article)):
            return

        self.incidentBuffer.append(dict(
            incident_time=datetime.datetime.fromtimestamp(article[2]),
            created_on=datetime.datetime.now(),
            incident_location=self.state,
            abstract=article[4][:1020],
            url=article[6][:1020],
            incident_source=article[7],
            title=article[3][:1020]
        ))
        if len(self.incidentBuffer) > 100:
            insertIncidents(self.incidentBuffer)
            self.incidentBuffer.clear()

    def load_news(self, when="1d"):
        gne = GoogleNewsExtractor(self.__handler, self.__filter_by_id)
        for city in CITIES:
            self.city = city
            self.state = CITIES[city]
            gne.search_and_extract(
                QUERY + " " + self.city, when)
        if len(self.incidentBuffer) > 0:
            insertIncidents(self.incidentBuffer)
            self.incidentBuffer.clear()
