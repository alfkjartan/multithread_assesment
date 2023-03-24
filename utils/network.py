import sys
import time
import socket
import multiprocessing
from multiprocessing import shared_memory
from multiprocessing import connection
from threading import Thread, Event
from service.model.message import Message
from service.repository.repository import Repository

#import time
#from threading import Thread

class ServerSingletonMeta(type):
    """
    From https://refactoring.guru/design-patterns/singleton/python/example
    """

    _instances = {}

    def __call__(cls, *args, **kwargs):
        """
        Possible changes to the value of the `__init__` argument do not affect
        the returned instance.
        """
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]

class ClientConnection:
    """ Representation of the client side connection for communication over sockets.

    Attributes
    ----------
    host : str
       The ip_address of the server to connect to. Defaults to '127.0.0.1' 
    port : int
       The port to connect to. Defaults to 33333
    scket : Socket
       The socket to communicate with

    Methods
    -------
    is_available() -> bool
       Returns True if connection is established and data can be sent
    send(d : Message) -> bool
       Returns True if sending was successfully completed
       
    """

    def __init__(self, host : str, port : int):

        self.host = host
        self.port = port
        self.sckt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.available = True
        self.connected = False
            
    def is_available(self) -> bool:
        return self.available

        
    def __connect(self) -> None:
        con = self.sckt.connect((self.host, self.port))
        self.connected = True
        print("Client connected")

    def send(self, d : Message) -> bool:
        if not self.connected:
            self.__connect()

        msg = d.to_json().encode()
        msglen = len(msg)
        totalsent = 0
        while totalsent < msglen:
            sent = self.sckt.send(msg[totalsent:])
            if sent == 0:
                self.available = False
                return False
            else:
                totalsent = totalsent + sent
        return True

    def close(self):
        """ Called  by sensor when shutting down."""
        print("Closing down socket.")
        self.sckt.close()
        
class ServerConnection():
    """ Representation of the server side connection for communication over sockets.

    Singleton.

    Attributes
    ----------
    host : str
       The ip_address of the server to connect to. Defaults to '127.0.0.1' 
    port : int
       The port to connect to. Defaults to 33333
    scket : Socket
       The socket to communicate with

    Methods
    -------
    run() -> None
       Starts listening for connections
       
    """

    def __init__(self, sckt : socket.socket, repo : Repository):
        self.sckt = sckt
        self.repository = repo
        
    def __call__(self, stop_event : Event):
        """ Function run by thread. Receives data over the socket, parses and calls repository.
        
            Code adapted from https://docs.python.org/3/howto/sockets.html
       """
        while True:
            if stop_event.is_set():
                print(f"ServerConnection with socket {self.sckt} received stop signal")
                break
            self.repository.append(Message.from_json_str(self.__read()))
            
    def __read(self) -> str:
        """ Will read data from the socket and checking for opening and closing curly
            brackets. Returns when a string with balanced curly brackets is found.
            """
        opening_brackets = 0
        closing_brackets = 0
        
        chunks = []
        bytes_recd = 0
        # Read to find first opening bracket 
        while opening_brackets == 0:
            chunk = self.sckt.recv(1024)
            if chunk == b'':
                raise RuntimeError("socket connection broken")
            opening_brackets += chunk.count(b'{')
            closing_brackets += chunk.count(b'}')
            chunks.append(chunk)

        # Continue reading until balanced number of brackets
        while opening_brackets > closing_brackets:
            chunk = self.sckt.recv(2048)
            if chunk == b'':
                raise RuntimeError("socket connection broken")
            opening_brackets += chunk.count(b'{')
            closing_brackets += chunk.count(b'}')
            chunks.append(chunk)
            
        return b''.join(chunks)
        
class Server(metaclass=ServerSingletonMeta):
    """ Representation of the server side for communication over sockets. Listens for 
    connections, instantiates  ServerConnection objects and spawns threads to handle communication. 

    Attributes
    ----------
    host : str
       The ip_address of the server to connect to. Defaults to '127.0.0.1' 
    port : int
       The port to connect to. Defaults to 33333
    scket : Socket
       The socket to communicate with

    Methods
    -------
    run() -> None
       Starts listening for connections
       
    """

    def __init__(self, host : str, port : int, repository : Repository):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.repository = repository
        self.client_sockets = []

        
    def run(self, stop_event : Event):
        print(f"")
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen()
        print(f"Server {self.host}:{self.port} is listening.")
        while True:
            if stop_event.is_set():
                print("Server received stop signal.")
                self.server_socket.close()
                for cs in self.client_sockets:
                    cs.close()
                    
            client_sock, addr = self.server_socket.accept()

            self.client_sockets.append(client_sock)
            
            conn = ServerConnection(client_sock, self.repository)
            print("Server accepting connection")
            Thread(target=conn, args=[stop_event]).start()
    def close(self):
        print(f"Server host = {self.host} and port = {self.port} is closing down.")
        self.server_socket.close()
        for cs in self.client_sockets:
            cs.close()
        

class SMClientConnection:
    """ Represents the client side of the communication. Holds the shared memory and the condition 
    variable to synchronize access.
    """

    def __init__(self):
        #self.condition_var = multiprocessing.Condition() Not shared in child processes
        self.new_data_flag = shared_memory.SharedMemory(create=True, size = 1)
        self.new_data_flag.buf[0] = 0
        self.message = shared_memory.SharedMemory(create=True, size=2048)
        self.wait_period = 0.001 # Period to wait between checks of data read.
        
    def send(self, d : Message) -> bool:
        while self.new_data_flag.buf[0]:
            # The previous message has not been read. Wait for short period
            time.sleep(self.wait_period)
            
        msg = d.to_json().encode()
        msglen = len(msg)
        if msglen > len(self.message.buf):
            raise MemoryError("Message too long for shared memory buffer")

        self.message.buf[:msglen] = msg
        self.new_data_flag.buf[0] = 1 # Will signal consumer 

    def is_available(self):
        return True # Always there

    def close(self):
        """ Called by Sensor object when receiving stop signal."""
        print("Closing and unlinking shared memory for ", self)
        self.message.close()
        self.message.unlink()
        self.new_data_flag.close()
        self.new_data_flag.unlink()

class SMServerConnection:
    """ Code run in a separate thread which will block at client object waiting for update to the 
    shared memory (Message object). The message object is passed on to the repository.
    """

    def __init__(self, repository : Repository, client : SMClientConnection):
        self.repository = repository
        self.message = shared_memory.SharedMemory(client.message.name)
        self.new_data_flag = shared_memory.SharedMemory(client.new_data_flag.name)
        self.new_data_flag.buf[0] = 0
        self.wait_period = 0.001
    def run(self, stop_event : Event):
        print("ServerConnection ", self, " is running")
        while True:
            if stop_event.is_set():
                print("ServerConnection ", self, " received stop signal")
                self.message.close()
                self.new_data_flag.close()
                break

            try: 
                while not self.new_data_flag.buf[0]:
                    time.sleep(self.wait_period)
            except TypeError:
                # TypeError is raised as a consequence  when self.new_data_flag is unlinked in other thread.
                # Use this as a signal to exit
                print("ServerConnection ", self, " closing down.")
                self.message.close()
                self.new_data_flag.close()
                break

                
            m = SMServerConnection.chop_json(str(self.message.buf, 'utf8'))
            self.repository.append(Message.from_json_str(m))
            self.new_data_flag.buf[0] = 0

    def close(self):
        print("ServerConnection ", self, " Closing down")
        self.message.close()
        self.new_data_flag.close()
        
    def chop_json(j : str) -> str:
        """ Removes everything before and after a set of balanced curly brackets. 

        Tests
        -----
        >>> j = '{"id": 0, "name": "Sensor-1", "data": -49, "time_stamp": "2023"}GARBAGE'
        >>> jchopped = SMServerConnection.chop_json(j)
        >>> jchopped == '{"id": 0, "name": "Sensor-1", "data": -49, "time_stamp": "2023"}'
        True
        >>> SMServerConnection.chop_json(jchopped) == jchopped
        True
        >>> j2 = jchopped + '}garbage}'
        >>> jchopped2 = SMServerConnection.chop_json(j2)
        >>> jchopped2 == jchopped
        True
       """

        opening_brackets = 0
        closing_brackets = 0
        start_ind = -1
        end_ind = -1
        for ind, ch in zip(range(len(j)), j):
            if ch == '{':
                if start_ind < 0:
                    start_ind = ind
                opening_brackets += 1
            if ch == '}':
                closing_brackets += 1
                if opening_brackets == closing_brackets:
                    end_ind = ind
                    break
        return j[start_ind:end_ind+1]


class PipeClientConnection:
    """ Represents the client side of the communication by pipe.
    """

    def __init__(self, client_conn : connection.Connection ):
        self.pipe = client_conn
        
    def send(self, d : Message) -> bool:
        self.pipe.send(d.to_json())
        return True
    def is_available(self):
        return True # Always there

    def close(self):
        print("Closing down pipe.")
        self.pipe.close()
        
class PipeServerConnection:
    """ Code run in a separate thread which will block at client object waiting for update to the 
    shared memory (Message object). The message object is passed on to the repository.
    """

    def __init__(self, repository : Repository, server_conn : connection.Connection ):
        self.repository = repository
        self.pipe = server_conn
        
    def run(self, stop_event : Event):
        print("ServerConnection ", self, " is running")
        while True:
            if stop_event.is_set():
                print("ServerConnection ", self, " is closing down")
                self.pipe.close()
                break
                
            try:
                j_str = self.pipe.recv()
            except EOFError:
                print("ServerConnection ", self, " is closing down")
                self.pipe.close()
                break
            
            self.repository.append(Message.from_json_str(j_str))

    def close(self):
        print("Server pipe closing down.")
        self.pipe.close()
        
class Connection:
    """ Factory class for instantiating connection objects that handle the communication between sensors and repository.

    The objects returned implement a method `run()` which should be run in a separate thread.

    Methods (all static)
    -------------------
    create_server( host : str, port : int, repository : Repository ) -> Server
    create_client_connection( host : str, port : int) -> ClientConnection
    create_memory_connection( repository : Repository) -> (SMServerConnection, SMClientConnection)
    create_pipe_connection( repository : Repository) -> (PipeServerConnection, PipeClientConnection)
    """


    def create_socket_connection(repository, host='127.0.0.1', port=33331):
        return ( Server(host, port, repository), ClientConnection(host, port) )

    def create_memory_connection(repository : Repository) -> (SMServerConnection, SMClientConnection):
        client = SMClientConnection()
        server = SMServerConnection(repository, client) # The shared memory is attribute of the client 
        return (server, client)

    def create_pipe_connection(repository : Repository) -> (PipeServerConnection, PipeClientConnection):
        client_conn, server_conn = multiprocessing.Pipe()
        client = PipeClientConnection(client_conn)
        server = PipeServerConnection(repository, server_conn) # The shared memory is attribute of the client 
        return (server, client)

