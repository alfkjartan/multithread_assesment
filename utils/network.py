import sys
import time
import socket
import multiprocessing
from multiprocessing import shared_memory
from multiprocessing import connection
from threading import Thread
from service.model.message import Message
from service.repository.logging import Logger

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
        print("Client connected. Type of return value ", type(con), file=sys.stderr)

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
            
class ServerConnection(metaclass=ServerSingletonMeta):
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

    def __init__(self, sckt : socket.socket, logger : Logger):
        self.sckt = sckt
        self.logger = logger
        
    def __call__(self):
        """ Function run by thread. Receives data over the socket, parses and calls logger.
        
            Code adapted from https://docs.python.org/3/howto/sockets.html
       """
        while True:
            self.logger.append(Message.from_json_str(self.__read()))
            
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
        
class Server:
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

    def __init__(self, host : str, port : int, logger : Logger):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.logger = logger

    def run(self):
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen()
        print("Server listening")
        while True:
            client_sock, addr = self.server_socket.accept()
            conn = ServerConnection(client_sock, self.logger)
            print("Server accepting connection")
            Thread(target=conn).start()
            

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

        print("Client got new data: ", d.to_json(), file=sys.stderr)
        self.message.buf[:msglen] = msg
        self.new_data_flag.buf[0] = 1 # Will signal consumer 

    def is_available(self):
        return True # Always there

        

class SMServerConnection:
    """ Code run in a separate thread which will block at client object waiting for update to the 
    shared memory (Message object). The message object is passed on to the logger.
    """

    def __init__(self, logger : Logger, client : SMClientConnection):
        self.logger = logger
        self.message = shared_memory.SharedMemory(client.message.name)
        self.new_data_flag = shared_memory.SharedMemory(client.new_data_flag.name)
        self.new_data_flag.buf[0] = 0
        self.wait_period = 0.001
    def run(self):
        print("ServerConnection ", self, " is running")
        while True:
            while not self.new_data_flag.buf[0]:
                time.sleep(self.wait_period)
        
            #print("ServerConnection waiting  on ", self.cv, file=sys.stderr)
            m = SMServerConnection.chop_json(str(self.message.buf, 'utf8'))
            print("Server got new data", m )
            self.logger.append(Message.from_json_str(m))
            self.new_data_flag.buf[0] = 0

    def chop_json(j : str) -> str:
        """ Removes everything after the last curly bracket. """
        jrev = j[::-1] # Reverses the string. 
        if jrev.index('}') == 0:
            #String is ok
            return j
        
        _, p, s = jrev.partition('}')
        return (p + s)[::-1]


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

class PipeServerConnection:
    """ Code run in a separate thread which will block at client object waiting for update to the 
    shared memory (Message object). The message object is passed on to the logger.
    """

    def __init__(self, logger : Logger, server_conn : connection.Connection ):
        self.logger = logger
        self.pipe = server_conn
        
    def run(self):
        print("ServerConnection ", self, " is running")
        while True:
            j_str = self.pipe.recv()
            self.logger.append(Message.from_json_str(j_str))

class Connection:
    """ Factory class for instantiating connection objects that handle the communication between sensors and logger.

    The objects returned implement a method `run()` which should be run in a separate thread.

    Methods (all static)
    -------------------
    create_server( host : str, port : int, logger : Logger ) -> Server
    create_client_connection( host : str, port : int) -> ClientConnection
    create_memory_connection( logger : Logger) -> (SMServerConnection, SMClientConnection)
    create_pipe_connection( logger : Logger) -> (PipeServerConnection, PipeClientConnection)
    """


    def create_socket_connection(logger, host='127.0.0.1', port=33331):
        return ( Server(host, port, logger), ClientConnection(host, port) )

    def create_memory_connection(logger : Logger) -> (SMServerConnection, SMClientConnection):
        client = SMClientConnection()
        server = SMServerConnection(logger, client) # The shared memory is attribute of the client 
        return (server, client)

    def create_pipe_connection(logger : Logger) -> (PipeServerConnection, PipeClientConnection):
        client_conn, server_conn = multiprocessing.Pipe()
        client = PipeClientConnection(client_conn)
        server = PipeServerConnection(logger, server_conn) # The shared memory is attribute of the client 
        return (server, client)

