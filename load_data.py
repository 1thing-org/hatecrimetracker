
from incidents import insertIncidents
import json
import datetime
from geopy.geocoders import Nominatim

STATES = {
    "Alabama" : "AL",
    "Alaska" : "AK",
    "Arizona" : "AZ",
    "Arkansas" : "AR",
    "California" : "CA",
    "Colorado" : "CO",
    "Connecticut" : "CT",
    "Delaware" : "DE",
    "Florida" : "FL",
    "Georgia" : "GA",
    "Hawaii" : "HI",
    "Idaho" : "ID",
    "Illinois" : "IL",
    "Indiana" : "IN",
    "Iowa" : "IA",
    "Kansas" : "KS",
    "Kentucky" : "KY",
    "Louisiana" : "LA",
    "Maine" : "ME",
    "Maryland" : "MD",
    "Massachusetts" : "MA",
    "Michigan" : "MI",
    "Minnesota" : "MN",
    "Mississippi" : "MS",
    "Missouri" : "MO",
    "Montana" : "MT",
    "Nebraska" : "NE",
    "Nevada" : "NV",
    "New Hampshire" : "NH",
    "New Jersey" : "NJ",
    "New Mexico" : "NM",
    "New York" : "NY",
    "North Carolina" : "NC",
    "North Dakota" : "ND",
    "Ohio" : "OH",
    "Oklahoma" : "OK",
    "Oregon" : "OR",
    "Pennsylvania" : "PA",
    "Rhode Island" : "RI",
    "South Carolina" : "SC",
    "South Dakota" : "SD",
    "Tennessee" : "TN",
    "Texas" : "TX",
    "Utah" : "UT",
    "Vermont" : "VT",
    "Virginia" : "VA",
    "Washington" : "WA",
    "West Virginia" : "WV",
    "Wisconsin" : "WI",
    "Wyoming" : "WY"
}
def loadData(fileName):
    incidents = []
    with open(fileName) as f:
        data = json.load(f)
        for item in data:
            '''
            "attributes": {
                            "Date_of_incident": "2/5/2020",
                            "Place_of_Incident": "New York, NY",
                            "Summary": "A woman wearing a face mask was punched and kicked by a man who called her \"diseased\".",
                            "News_Source": "https://www.nbcnews.com/news/us-news/coronavirus-hate-attack-woman-face-mask-allegedly-assaulted-man-who-n1130671?cid=sm_npd_nn_tw_ma",
                            "Latitude": 40.718353,
                            "Longitude": -73.993869,
                            "__OBJECTID": 0
                        }
            '''         
            record = item.get("attributes")
            if  not record.get("Place_of_Incident") in ADDR_STATE or "BAD" == ADDR_STATE[record.get("Place_of_Incident")]:
                continue
            try:
                incidents.append(dict(
                    incident_time=datetime.datetime.strptime(record.get("Date_of_incident"), '%m/%d/%Y'),
                    created_on=datetime.datetime.now(),
                    incident_location=ADDR_STATE[record.get("Place_of_Incident")],
                    abstract=record.get("Summary"),
                    url=record.get("News_Source"),
                    incident_source="racismiscontagious",
                    title=record.get("Summary")               
                ))
            except Exception as e:
                print(e)
    insertIncidents(incidents)

geolocator = Nominatim(user_agent="geoapiExercises")

class IncidentBuffer:
    def __init__(self):
        self.incidents=[]

    def add(self, record):
        try:
            location = geolocator.reverse("{},{}".format(record.get("Latitude"),record.get("Longitude")))
            (state, zip, country) = location.address.split(",")[-3:]
            if country.strip() != "United States":
                return
            state = state.strip()
            print("State:"+state)
            self.incidents.append(dict(
                    incident_time=datetime.datetime.strptime(record.get("Date_of_incident"), '%m/%d/%Y'),
                    created_on=datetime.datetime.now(),
                    incident_location=STATES[state],
                    abstract=record.get("Summary"),
                    url=record.get("News_Source"),
                    incident_source="racismiscontagious",
                    title=record.get("Summary")               
                ))
        except Exception as e:
            print(e)

    def get_incidents(self):
        return self.incidents

class Counter:
    def __init__(self):
        self.count=0

    def inc(self):
        self.count+=1

    def get_count(self):
        return self.count

def traverse(json, buffer):
    if isinstance(json, list):
        for value in json:
            traverse(value, buffer)
    else:
        if type(json) is dict:
            for key in json:
                if key == "attributes":
                    print(json[key])
                    buffer.add(json[key])
                    continue
                traverse(json[key], buffer)

def traverse_file(fileName):
    with open(fileName) as f:
        buffer = IncidentBuffer()
        traverse(json.load(f), buffer)
        print("Count:{}".format(len(buffer.get_incidents())))
        insertIncidents(buffer.get_incidents())
        return len(buffer.get_incidents())