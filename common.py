class Incident(object):
    def __init__(self, id,incident_time,created_on,title,abstract,incident_source, incident_location=None, url=None):
        super().__init__()
        self.id = id
        self.incident_time = incident_time
        self.created_on = created_on
        self.title = title
        self.abstract = abstract
        self.incident_location = incident_location
        self.url = url
        self.incident_source = incident_source

    @staticmethod
    def fromDict(dict):
        if dict is not None:
            return User(name=dict.get('name'), email=dict.get('email'))
        return None
