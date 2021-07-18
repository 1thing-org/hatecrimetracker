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

    def to_dict(self):
        return {
            "id" : self.id,
            "incident_time" : self.incident_time,
            "created_on" : self.created_on,
            "title" : self.title,
            "abstract" : self.abstract,
            "incident_location" : self.incident_location,
            "url" : self.url,
            "incident_source" : self.incident_source
        }

class User(object):
    def __init__(self, name, email) -> None:
        super().__init__()
        self.name = name
        self.email = email

    @staticmethod
    def from_dict(dict):
        if dict is not None:
            return User(name=dict.get('name'), email=dict.get('email'))
        return None

    def to_dict(self):
        return {
            "name": self.name,
            "email": self.email
        }
