import numpy as np
import random
import sys
import getopt
from datetime import datetime
from multiprocessing import Event as ProcessEvent
from multiprocessing import Process
from threading import Thread
from threading import Event as ThreadEvent
from functools import partial
from service.repository.logging import Logger
from service.repository.repository import Repository
from utils.network import Connection
from service.model.message import Message
from sensors.base_sensor import Sensor

if __name__ == '__main__':
    # Default settings
    connection_type = 'socket'
    host = '127.0.0.1'
    port = 33332
    num_sensors = 5
    csv_logfile = datetime.now().strftime("sensorlog-%Y-%m-%d.csv")
    sqlite_dbfile = datetime.now().strftime("sensorlog-sqlite-%Y-%m-%d.db")
    log_to_screen = False
    log_to_plot = False
    
    try:
        opts, args = getopt.getopt(sys.argv[1:],"n:c:p:f:d:s",
                                   ["num_sensors=", "connection_type=", "plot", 
                                    "csv_file", "db_file", "screen_output"])
    except getopt.GetoptError:
        sys.exit(2)

    for opt, arg in opts:
        if opt in ("-n", "--num_sensors"):
            num_sensors = int(arg)
        elif opt in ("-c", "--connection_type"):
            connection_type = arg
        elif opt in ("-p", "--plot"):
            log_to_plot = True
        elif opt in ("-f", "--csv_file"):
            csv_logfile = arg
        elif opt in ("-d", "--db_file"):
            sqlite_dbfile = arg
        elif opt in ("-s", "--screen_output"):
            log_to_screen = True


            
    # Setting up the logger
    logger = Logger()
    logger.add_repository(Repository.csv_repository(csv_logfile))
    #TODO implement logging to sqlite database
    if log_to_screen: logger.add_repository(Repository.screen_dump())
    if log_to_plot: logger.add_repository(Repository.plot(num_sensors))
        
    if connection_type == 'socket':
        connection_factory = partial(Connection.create_socket_connection, host=host, port=port)
    elif connection_type == 'shared_memory':
        connection_factory = Connection.create_memory_connection
    elif connection_type == 'pipe':
        connection_factory = Connection.create_pipe_connection

    # Creating Event objects to signal stop of simulation
    proc_stop_event = ProcessEvent()
    thread_stop_event = ThreadEvent()

    # Setting up connections to handle communication
    sensor_connections = []
    server_connections = [] # Need acces to these for closing down gracefully
    server_threads = []
    for _ in range(num_sensors):
        server_connection, client_connection = connection_factory(logger) 
        server_thread = Thread(target = server_connection.run, args = [thread_stop_event])
        if not server_thread.is_alive():
            server_thread.start()
        server_threads.append(server_thread)
        server_connections.append(server_connection)
        sensor_connections.append(client_connection)
          
    # Creating and spawning the sensors
    dts = np.arange(1, num_sensors+2) # The sampling period of the sensors
    sensors = [Sensor(id, f'Sensor-{dt}', sampling_period = dt,
                      probe = lambda : random.randint(-100, 100),
                      connection = conn) for id, dt, conn in zip(range(num_sensors), dts, sensor_connections)]
    print("Created sensor processes.")
    sensor_processes = [Process(target=s.run, args=[proc_stop_event]) for s in sensors]
    for p in sensor_processes:
        p.start()
    print("Started sensors.")

    input = input("Press return to end simulation")

    thread_stop_event.set()
    proc_stop_event.set()
    
    for p in sensor_processes:
        p.join()

    print("All sensor processes done.")

    for sc in server_connections:
        sc.close()
        
    for s in server_threads:
        s.join()

    print("All server threads done. Exiting.")

    
