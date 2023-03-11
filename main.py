import numpy as np
import random
import sys
import getopt
from datetime import datetime
from multiprocessing import Process
from threading import Thread
from service.repository.logging import Logger
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
    
    try:
        opts, args = getopt.getopt(sys.argv[1:],"n:c:h:p:f:d:s",
                                   ["num_sensors=", "connection_type=", "host=", "port=",
                                    "csv_file", "db_file", "screen_logger"])
    except getopt.GetoptError:
        sys.exit(2)

    for opt, arg in opts:
        if opt in ("-n", "--num_sensors"):
            num_sensors = int(arg)
        elif opt in ("-c", "--connection_type"):
            connection_type = arg
        elif opt in ("-h", "--host"):
            host = arg
        elif opt in ("-p", "--port"):
            port = int(arg)
        elif opt in ("-f", "--csv_file"):
            csv_logfile = arg
        elif opt in ("-d", "--db_file"):
            sqlite_dbfile = arg
        elif opt in ("-s", "--screen_logger"):
            log_to_screen = True


    print(connection_type)

    # Setting up the logger
    logger = Logger()
    logger.add_csv_repository(csv_logfile)
    #TODO implement logging to sqlite database
    if log_to_screen:
        logger.add_screen()

        
    if connection_type == 'socket':
        connection_factory = Connection.create_socket_connection
        # Setting up and starting the server
        #server = Connnection.create_server(host, port, logger)
        #server_thread = Thread(target = server.run)
        #print("Running server thread")
        #server_thread.start()
        #server_threads = [server_thread,]
        # Creating the connection objects
        #sensor_connections = [Connection.create_client_connection(host, port) for _ in range(num_sensors)]
    elif connection_type == 'shared_memory':
        connection_factory = Connection.create_memory_connection
    elif connection_type == 'pipe':
        connection_factory = Connection.create_pipe_connection

    sensor_connections = []
    server_threads = []
    for _ in range(num_sensors):
        server_connection, client_connection = connection_factory(logger) 
        server_thread = Thread(target = server_connection.run)
        if not server_thread.is_alive():
            server_thread.start()
        server_threads.append(server_thread)
        sensor_connections.append(client_connection)
            
    # Creating and spawning the sensors
    dts = np.arange(1, num_sensors+2) # The sampling period of the sensors
    sensors = [Sensor(id, f'Sensor-{dt}', sampling_period = dt,
                      probe = lambda : random.randint(-100, 100),
                      connection = conn) for id, dt, conn in zip(range(num_sensors), dts, sensor_connections)]
    print("Created sensor processes")
    sensor_processes = [Process(target=s.run) for s in sensors]
    for p in sensor_processes:
        p.start()
    print("Started sensors")

    
    for p in sensor_processes:
        p.join()
    for s in server_threads:
        s.join()

    
