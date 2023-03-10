import numpy as np
import random
from multiprocessing import Process
from threading import Thread
from service.repository.logging import Logger
from utils.network import Server, ClientConnection 
from service.model.message import Message
from sensors.base_sensor import Sensor

if __name__ == '__main__':
    
    # Printing messages to screen and writing to file 
    logger = Logger()
    logger.add_csv_repository("sensorlog.csv").add_screen()

    # Setting up and starting the server
    host = '127.0.0.1'
    port = 33332
    server = Server(host, port, logger)
    server_thread = Thread(target = server.listen)
    print("Running server thread")
    server_thread.start()

    # Creating and spawning the sensors
    N = 5 # The number of sensors
    dts = np.arange(1, 7) # The sampling period of the sensors
    sensors = [Sensor(id, f'Sensor-{dt}', sampling_period = dt,
                      probe = lambda : random.randint(-100, 100),
                      connection = ClientConnection(host, port)) for id, dt in zip(range(N), dts)]
    print("Created sensor processes")
    sensor_processes = [Process(target=s.run) for s in sensors]
    for p in sensor_processes:
        p.start()
    print("Started sensors")
    for p in sensor_processes:
        p.join()
        

    server_thread.join()

    
