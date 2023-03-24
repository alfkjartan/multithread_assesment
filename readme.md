
# Multithread assessment - Problem description

## The objective: 
Create an application that simulates sensors logging info to a persistent datasource.
With the following restraints:
- Simulate the interaction between sensors and network, the network should have a limit of 5 messages maximum at once.
- Use multithreading, create 5 sensors that should be registering to the log service. All five sensors should work 
simultaneously without blocking each other and use same network restrains.
- Sensors should log every 5 seconds, and a timestamp should persist onto datasource.
- Sensors most generate the following info, timestamp, sensor name, value (integer between -100 and 100).
- Model, most define all properties needed to persist data into datasource.
- Model most have a timestamp type, id, sensor name, value.
- Repository class should contain all logic needed to use a file/memory database, and convert logic for model to allow 
insertion into database.
- Use PEP8 conventions for coding.

### EXTRA
- Sensors: create multiple sensors using the default sensor of 5 seconds delay as base, 
and use factory pattern to create multiple types sensors with varying delay time.
- Repository: create an implementation that allows to change datasource options before running.
- Use type hinting.

![Diagram solution](multithread_assesment.png)

Modify classes or create new ones as you find needed, also you are free to use whatever library you want.
Don't forget to include the requirements file.

# Solution
## Design principles
The most important principle in software design is to make the code easy to understand, extend and  maintain. Complexity is the enemy.
### Avoid unnecessary dependencies
Classes/modules must be connected to make the software have the functionality it should and work as intended. But dependencies should be kept to a minimum so that changes in one class/module do not break code in other parts of the software.
### Encapsulate what varies
Those parts of the code that we expect to be subject to change in the future should be isolated from the parts that can be assumed to be stable. It should be easy to replace parts that are subject to frequent changes without having to modify other parts.
### Classes should be closed for modification - open for extension
Classes should be possible to extend with new functionality without modifying existing code. This is one of the reasons composition is preferred over inheritance.
### Strive for deep classes and functions
According to [John Ousterhout](https://youtu.be/bmSAYlu0NcY): Classes and functions should provide substantial functionality, but have a simple interface. The purpose is to make classes and functions easy to use. This will reduce complexity. 

## Design requirements
### Constraints
- Each simulated sensors should run in a different process. This is closest to a real scenario.
- The system should close down gracefully, releasing any resources before shutting down.
### Candidates for variation
- The **storage used for logging**. Logging could go to file (csv, sqlite3), to network-connected SQL-database, saved in memory, or simply printed to screen.  And in any combinations of the previous.
- The part of the sensor that actually **acquires data**. This is referred to here as the probe. In the simulation model developed here this is just a function that returns a number. In practice, it would be something more interesting.
- The **data model**. This is related to the previous item. Some sensors will generate data of different kind, including array-like data. Whenever possible, objects that receives data should be agnostic to the structure of the message, to avoid dependencies. 
- The **connection between the sensors and the repository**. There are different ways of implementing  inter-process communications. Here, tcp sockets, shared memory, pipes and queues will be used. Importantly, the design should make it easy to switch the type of communication.
- The **number of sensors**.
## Design
### UML
#### Class diagram
![Class diagram](./latex/uml.png)
#### Sequence diagram
![Sequence diagram](./latex/seqdiag.png)

### Data model
The `service.model.Message` class represents the data generated by the sensors which are to be logged. According to the specifications, the attributes include time stamp, unique ID, name, and data value. The message objects are serialized in the form of json-strings for inter-process communication. Thus the messages must be able to be represented as json and also reconstructed by parsing a json-string.
### Sensors - clients
The `sensors.base_sensor.Sensor` objects run in separate processes, but with only a single main-thread. The sensors are considered to be the clients in the solution. This makes sense from the objective of the system, which is to provide logging functionality for sensors generating data. The `Sensor` object has two important attributes:
  * `probe` which is a function or callable object that returns a data value. 
  * `connection` At instantiation, the object receives the client-part of a client-server connection pair. The connection object provides a `send( m : Message )` method for sending data to the logger. 
### Communication
### Client side
The client-part of the connection pairs belong to the `Sensor` object, and run in its process. 
#### Server side
The server-part runs in a separate thread. In all three types of communication (socket, shared_memory, pipe), the server-part reads a json-string, reconstructs the `Message` object, and calls `append( m : Message)` on the `Repository` object.
### Logging
The `repository.Repository` class provides a simple interface for logging `Message` objects, by calling `append(m : Message)` method. The [composite pattern](https://refactoring.guru/design-patterns/composite/python/example) is used so that from the perspective of the calling object, a single and several (composite) repository objects have the same interface.  The repository object maintains a list of other `service.repository.Repository` objects, and forwards the call to `append()` to each of the children repositories. Repository objects can be added to- and removed from the list at runtime. The `Repository` object receives calls from several threads, from all the server-side connection objects that are running. The call to `append` on each concrete repository subclass is thread-safe.

The `Repositiory` objects are in essence like lists, and in fact a regular `list` object can be used as a repository to store incoming messages in memory. There are three custom `Repository` classes defined. 
  * `CSVRepository` appends the data of each message as a row to a csv file. 
  * `PlotRepository` starts a window in a separate process (needed since tkinter / matplotlib can only run in the main thread), and forwards data to be plotted using a `multiprocessing.Queue` object for inter-process communication. 
  * `ScreenRepository` simply prints the data to the screen
## Design patterns used
  * [Factory Method.](https://refactoring.guru/design-patterns/factory-method) This is used to create server-client connection pairs for different type of communication. See [network.py](./utils/network.py).
  * [Singleton.](https://refactoring.guru/design-patterns/singleton) This pattern is used 
	to ensure there is only one `Server` object listening for connections on the server socket. 
  * [Composite.](https://refactoring.guru/design-patterns/composite) Used to make a single or a collection of repository object have the same interface, and to make it easy to add new repository sublasses. See [repository.py](./service/repository/repository.py).
  * [Strategy.](https://refactoring.guru/design-patterns/strategy) Used in the `Sensor` class, to separate the data acquisition part (the `probe` callable) which can the vary depending on the type of sensor being simulated. See [base_sensor.py](./sensors/base_sensor.py).
  * [Iterator.](https://refactoring.guru/design-patterns/iterator) Implemented in the `Repository` and `CSVRepository` classes. Note that when iterating over to the composite `Repository` object, iteration will be over all the child-repositories. See [repository.py](./service/repository/repository.py).
  
## Multithreading and multiprocessing implemented
  * Each sensor runs in a separate process. Three different types of inter-process communication is implemented:
	* [Network socket.](https://docs.python.org/3/library/socket.html) This is very flexible, and allows for communication between different computers (distributed computing).
	* [Shared memory.](https://docs.python.org/3.8/library/multiprocessing.shared_memory.html) This is the fastest possible way of communication, by sharing physical memory space, since no copying of data is nvolved. On the other hand, this is not really an issue for this application, since the  messages sent from the sensors are small in size.
	* [Pipes.](https://docs.python.org/3.8/library/multiprocessing.html#pipes-and-queues) This is a more convenient way of implementing communication than shared memory. Processes write to- and read from the pipe, and the underlying synchronization of access to the memory is handled for you.
 * Since it was necessary that matplotlib runs in a main thread to be able to plot data, a seperate process is started in `PlotRepository`, and communication is over a [Queue,](https://docs.python.org/3.8/library/multiprocessing.html#pipes-and-queues) to which the two processes put and get elements.

## Running the simulation
The main script takes the following options and arguments:
- `--connection_type` can be `socket`|`pipe`|`shared_memory`
- `--port` exects and integer, i.e. the port number. Local host 127.0.0.1 is used. The setting has no effect unless connection type is socket.
- `--system_data` is a flag. If set, the sensors get data about the system from `psutil` instead of random numbers.
- `--num_sensors` expects an integer. If `--system_data` is set, it has no effect.
- `--csv_file` expects a string. The file to log to.
- `--log_to_screen` is a flag. If set, sensor data will be dumped to the screen (in addition to logged to file).
- `--log_to_plot` is a flag. If set, sensor data will be plotted (in addition to logged to file).


