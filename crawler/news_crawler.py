
import csv
import datetime
from os import stat
from incidents import insertIncidents
from crawler.pygooglenews_util import GoogleNewsExtractor

QUERY = 'anti-asian attack'

CITIES = {
    "New York":"NY",
    "Los Angeles":"CA",
    "Chicago":"IL",
    "Houston":"TX",
    "Philadelphia":"PA",
    "Phoenix":"AR",
    "San Antonio":"TX",
    "San Diego":"CA",
    "Dallas":"TX",
    "San Jose":"CA",
    "Austin":"TX",
    "Indianapolis":"IN",
    "Jacksonville":"FL",
    "San Francisco":"CA",
    "Columbus":"OH",
    "Charlotte":"NC",
    "Fort Worth":"TX",
    "Detroit":"MI",
    "El Paso":"TX",
    "Memphis":"TN",
    "Seattle":"WA",
    "Denver":"CO",
    "Washington":"DC",
    "Boston":"MA",
    "Nashville":"TN"
}
class NewsCrawler:
    

    def __init__(self, state = "NY", city ="New York"):
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
        
    # callback to be called by NewsExtractor
    def __handler(self, article):
        # [tmp_id, tmp_ts, tmp_publish_ts, tmp_title, tmp_abstract, tmp_location, tmp_url, tmp_source]
        print("id: {}\n publish time: {}\n title: {}\n abstract: {}\n location:{}\n state:{}\n url:{}\ntags:{}".format(
            article[0], datetime.datetime.fromtimestamp(article[2]), article[3], article[4], article[5], self.state, article[6], str(article[8])
        ))
        self.incidentBuffer.append({
            "incident_time" : datetime.datetime.fromtimestamp(article[2]),
            "created_on"    : datetime.datetime.now(),
            "incident_location": self.state,
            "abstract"  : article[4],
            "url"           : article[6],
            "incident_source": article[7],
            "title"         : article[3]
        })
        if len(self.incidentBuffer)>100:
            insertIncidents(self.incidentBuffer)
            self.incidentBuffer.clear()
        

    def load_news(self, time_end, num_days = datetime.timedelta(1)):
        gne = GoogleNewsExtractor(self.__handler, self.__filter_by_id)
        for city in CITIES:
            self.city = city
            self.state = CITIES[city]
            gne.search_and_extract(QUERY + " " + self.city, time_end, self.TIME_DELTA)
        if len(self.incidentBuffer)>0:
            insertIncidents(self.incidentBuffer)
            self.incidentBuffer.clear()