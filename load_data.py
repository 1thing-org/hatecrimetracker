import traceback
from firestore.incidents import insertIncident
import json
import datetime
import re
import csv

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
ZIP_TO_STATE = dict()

def load_zip_to_state():
    ZIP_TO_STATE.clear()
    with open('uszips.csv', newline='') as csvfile:
        csvreader = csv.reader(csvfile, delimiter=',', quotechar='"')
        for row in csvreader:
            if row[0] == 'zip' or not row[0]:
                continue
            ZIP_TO_STATE[row[0]] = row[4]
def get_date(record):
    for pattern in ["%B, %Y", '%m/%d/%Y', '%m/%d/%y']:
        try:
            return datetime.datetime.strptime(record.get("Date_of_incident"), pattern)
        except:
            pass
    for pattern in ["%B, %Y", '%m/%d/%Y', '%m/%d/%y']:
        try:
            return datetime.datetime.strptime(record.get("Date"), pattern)
        except:
            pass
    raise Exception("Invalid date")

# def loadData(fileName):
#     incidents = []
#     with open(fileName) as f:
#         data = json.load(f)
#         for item in data:
#             '''
#             "attributes": {
#                             "Date_of_incident": "2/5/2020",
#                             "Place_of_Incident": "New York, NY",
#                             "Summary": "A woman wearing a face mask was punched and kicked by a man who called her \"diseased\".",
#                             "News_Source": "https://www.nbcnews.com/news/us-news/coronavirus-hate-attack-woman-face-mask-allegedly-assaulted-man-who-n1130671?cid=sm_npd_nn_tw_ma",
#                             "Latitude": 40.718353,
#                             "Longitude": -73.993869,
#                             "__OBJECTID": 0
#                         }
#             '''         
#             record = item.get("attributes")
#             if  not record.get("Place_of_Incident") in ADDR_STATE or "BAD" == ADDR_STATE[record.get("Place_of_Incident")]:
#                 continue
#             try:
#                 incidents.append(dict(
#                     incident_time=get_date(record),
#                     created_on=datetime.datetime.now(),
#                     incident_location=ADDR_STATE[record.get("Place_of_Incident")],
#                     abstract=record.get("Summary"),
#                     url=record.get("News_Source"),
#                     incident_source="racismiscontagious",
#                     title=record.get("Summary")               
#                 ))
#             except Exception as e:
#                 print(e)
#                 print(record)
#     insertIncidents(incidents)


class IncidentBuffer:
    def __init__(self):
        self.incidents=[]

    def get_state(self, incident):
        if len(ZIP_TO_STATE) == 0:
                load_zip_to_state()
                print("Zip to state:{}".format(ZIP_TO_STATE.values))
        # Location_City_State_ : Garden Ln & Los Gatos Blvd, Los Gatos, CA 95032
        #                           Sunset District, San Francisco, CA
        #                           Outer Sunset, San Francisco, CA
        # Place_of_Incident: "New York, NY",
        if incident.get("Place_of_Incident"):
            state = incident['Place_of_Incident'].split(',')[-1].strip()
            if state != "":
                return state

        if incident.get("Location_City_State_"):
            m = re.search('(\d{5})', incident['Location_City_State_'])
            if m:
                for group in m.groups():
                    if group in ZIP_TO_STATE:
                        return ZIP_TO_STATE[group] 
            for str in incident['Location_City_State_'].split(','):
              str = str.strip()
              if str in ZIP_TO_STATE.values():
                  return str

        return ""
        
    def add(self, record):
        try:
            # location = geolocator.reverse("{},{}".format(record.get("Latitude"),record.get("Longitude")))
            # (state, zip, country) = location.address.split(",")[-3:]
            # if country.strip() != "United States":
            #     return
            # state = state.strip()
            # print("State:"+state)
            state = self.get_state(record)
            if state == "":
                print("Failed to find state:{}".format(record))
                return

            self.incidents.append(dict(
                    incident_time=get_date(record),
                    created_on=datetime.datetime.now(),
                    incident_location=state,
                    abstract=record.get("Summary"),
                    url=record.get("News_Source"),
                    incident_source="racismiscontagious",
                    title=record.get("Summary")               
                ))
        except Exception as e:
            print(e)
            print (traceback.format_exc())
            print(record)

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
                    buffer.add(json[key])
                    continue
                traverse(json[key], buffer)

COLUMNS = ["incident_time", "created_on", "incident_location",  "abstract", "url", "incident_source", "title"]
def write_to_csv(incidents):
    with open('loadtata_result.csv', 'w', newline='') as csvfile:
        csvwriter = csv.writer(csvfile, delimiter=',',
                                quotechar='"', quoting=csv.QUOTE_MINIMAL)
        csvwriter.writerow(['id']+COLUMNS)
        id = 0
        titles = dict()
        for incident in incidents:
            if incident["title"] in titles:
                continue
            titles[incident["title"]] = 1
            csvwriter.writerow([id] + [incident[f] for f in COLUMNS]) 
            id += 1

def traverse_file(fileName):
    load_zip_to_state()
    with open(fileName) as f:
        buffer = IncidentBuffer()
        traverse(json.load(f), buffer)
        print("Count:{}".format(len(buffer.get_incidents())))
        for incident in buffer.get_incidents():
            insertIncident(incident=incident)
        write_to_csv(buffer.get_incidents())
        return len(buffer.get_incidents())