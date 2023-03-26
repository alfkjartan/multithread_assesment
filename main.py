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
from service.repository.repository import Repository
from utils.network import Connection
from service.model.message import Message
from sensors.base_sensor import Sensor
from sensors.probe import *

if __name__ == '__main__':
    # Default settings
    connection_type = 'socket'
    host = '127.0.0.1'
    port = 33330
    num_sensors = 5
    csv_logfile = datetime.now().strftime("sensorlog-%Y-%m-%d-.csv")
    sqlite_dbfile = datetime.now().strftime("sensorlog-%Y-%m-%d-%H-%M-%S.db")
    log_to_screen = False
    log_to_plot = False
    system_sensor_data = False
    
    try:
        opts, args = getopt.getopt(sys.argv[1:],"n:c:p:c:s:o:r",
                                   ["num_sensors=", "connection_type=", "plot", 
                                    "csv_file", "screen_output", "system_data",
                                    "port="])
    except getopt.GetoptError:
        print("Error in parsing arguments")
        sys.exit(2)

    for opt, arg in opts:
        if opt in ("-n", "--num_sensors"):
            num_sensors = int(arg)
        elif opt in ("-c", "--connection_type"):
            connection_type = arg
        elif opt in ("-p", "--plot"):
            log_to_plot = True
            num_sensors = 4
        elif opt in ("-f", "--csv_file"):
            csv_logfile = arg
        elif opt in ("-s", "--screen_output"):
            log_to_screen = True
        elif opt in ("--system_data"):
            # Use functions from psutil module to generate sensor data 
            system_sensor_data = True
        elif opt in ("--port"):
            # Use functions from psutil module to generate sensor data 
            port = int(arg)


            
    # Setting up the repositories. Both CSV and sqlite
    logger = Repository().sql(sqlite_dbfile).csv(csv_logfile)
    #logger.add_repository([])
    if log_to_screen: logger.screen_dump()
    if log_to_plot: logger.plot(num_sensors)
    
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
        sensor_connections.append(client_connection)
        
        if server_connections != []:
            if connection_type == 'socket':
                # Singleton server connection used with socket communication
                # Avoid starting new thread to serve the same ip adress
                pass
            else:
                # Shared memory or pipe communications
                server_thread = Thread(target = server_connection.run, args = [thread_stop_event])
                server_thread.start()
                server_connections.append(server_connection)
                server_threads.append(server_thread)

        else: # Empty list server_connections, so append the first
            server_thread = Thread(target = server_connection.run, args = [thread_stop_event])
            server_thread.start()
            server_connections.append(server_connection)
            server_threads.append(server_thread)

          
    # Creating and spawning the sensors
    if system_sensor_data:
        dts = [0.5, 5, 0.5, 0.5] # The sampling period of the sensors
        sensor_probes = {'CPU utilization (percent)' : cpu_utilization,
                         'Load average (divide with number of cpu cores)' : load_average,
                         'Memory available (Gb)' : memory_available,
                         'CPU temperature (Celcius)' : cpu_temp}
    else:
        dts = np.arange(1, num_sensors+2)/num_sensors # The sampling period of the sensors
        sensor_probes = {}
        for dt_ in range(num_sensors):
            sensor_probes[f'Sensor-{dt_}'] = lambda : random.randint(-100, 100)
            
    sensors = [Sensor(id, name, sampling_period = dt,
                      probe=sensor_probes[name],
                      connection = conn) \
               for id, name, dt, conn in zip(range(len(dts)), sensor_probes.keys(),
                                             dts, sensor_connections)]
    print("Created sensor processes.")
    sensor_processes = [Process(target=s.run, args=[proc_stop_event]) for s in sensors]
    for p in sensor_processes:
        p.start()
    print("Started sensors.")

    input("Press return to end simulation")

    thread_stop_event.set()
    proc_stop_event.set()
    
    for p in sensor_processes:
        p.join()

    print("All sensor processes done.")

    for sc in server_connections:
        sc.close()
        
    for s in server_threads:
        s.join()

    print("All server threads done.")


    print("\n\n-----------------------------------------------------------\n")
    print("Logged data\n")
    for m in logger:
        print(m)
    print("\n\n-----------------------------------------------------------\n")


