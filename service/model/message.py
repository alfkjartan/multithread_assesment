from typing import Any
from datetime import datetime
import json

class Message:
    """ Representation of the data generated by the sensors. 

    
    Attributes
    ----------
    ID : int
       The ID of the sensor that generated the data
    name : str
       The name of the sensor that generated the data
    time_stamp : datetime
    data : Any

    
    Methods
    -------
    to_json() -> str
       Returns a json string with the all the data.
    from_json(j : str)
       Replaces data fields with data in json string.

    Static methods
    --------------
    int_message() -> Message
       Returns an object for which the data field is an integer. 
     
    """

    def __init__(self, id : int, name : str, data : Any, time_stamp = None):
        self.id = id
        self.name = name
        self.set_data(data, time_stamp)

    def set_data(self, data : Any, time_stamp = None):
        self.data = data
        if time_stamp is None:
            # Take current time
            self.time_stamp = datetime.now().strftime("%Y-%m-%d_%H:%M:%S:%f")
        else:
            self.time_stamp = time_stamp
        
    def to_json(self) -> str:
        return json.dumps(self.__dict__)

    def from_json(self, j : str):
        jdict = json.loads(j)
        attrs = self.__dict__.keys()
        for key, val in jdict.items(): 
            if key in attrs:
                setattr(self, key, val)

        return self

    def from_json_str(j : str):
        m = Message(42, 'unknown', 1) # Just temporary
        return m.from_json(j)

    def int_message():
        return Message(-1, "Unknown", 1)
    
