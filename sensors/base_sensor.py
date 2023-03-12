from typing import Callable
import time
from threading import Event
from utils.network import ClientConnection
from service.model.message import Message

class Sensor:
    def __init__(self, id : int, name : str, sampling_period : float,
                 probe : Callable, connection : ClientConnection):

        self.id = id
        self.name = name
        self.dt = sampling_period
        self.probe = probe
        self.connection = connection
        
        self.message = Message(id, name, 0)
        
    def run(self, stop_event : Event):
        while True:
            time.sleep(self.dt)
            if stop_event.is_set():
                print(f"{self.name} received stop event. Closing connection.")
                self.connection.close()
                break
            self.acquire()
            if not self.connection.is_available():
                break
            self.connection.send(self.message)


    def acquire(self):
        self.data = self.probe()
        self.message.set_data(self.data)
        
        
