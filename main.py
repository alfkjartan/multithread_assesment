import multiprocessing
from service.repository.loggin import Logger
from utils.network import Server 
from service.model.message import Message

from  import Logging
from sensors.base_sensor import BaseSensor
from service.repository.repository import Repository
from utils.network import Network

if __name__ == '__main__':
    # Empty message. Needed by the server to parse incoming messages.
    message = Message.int_message()
    
    # Printing messages to screen and writing to file 
    logger = Logger()
    logger.add_csv_logger("sensorlog.csv").add_screen_logger()


    server = Server(
    
    repository = Repository()
    network = Network()
    sensors = BaseSensor(network)
    logging = Logging(repository, network)
