import socket
from service.model.message import Message
from logging.logging import Logger

#import time
#from threading import Thread

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
        try:
            self.__connect()
        except ConnectionResetError:
            self.available = False
            
    def is_available(self) -> bool:
        return self.available

        
    def __connect(self):
        self.sckt.connect((self.host, self.port))


    def send(self, d : Message) -> bool:
        msg = d.to_json()
        msglen = len(msg)
        totalsent = 0
        while totalsent < msglen:
            sent = self.sock.send(msg[totalsent:])
            if sent == 0:
                self.available = False
            totalsent = totalsent + sent

            
class ServerConnection
    """ Representation of the server side connection for communication over sockets.

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

    def __init__(self, sckt : socket.Socket, logger : Logger):
        self.sckt = sckt
        self.logger = logger
        
        def __call__(self):
        """ Function run by thread. Receives data over the socket, parses and calls logger.
        
        Code adapted from https://docs.python.org/3/howto/sockets.html
        """

        
        while True:
            self.logger.append(Message.from_json(self.__read())

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
                chunk = self.sock.recv(1024)
                if chunk == b'':
                    raise RuntimeError("socket connection broken")
                opening_brackets += chunk.count(b'{')
                closing_brackets += chunk.count(b'}')
                chunks.append(chunk)

            # Continue reading until balanced number of brackets
            while opening_brackets > closing_brackets:
                chunk = self.sock.recv(2048)
                if chunk == b'':
                    raise RuntimeError("socket connection broken")
                opening_brackets += chunk.count(b'{')
                closing_brackets += chunk.count(b'}')
                chunks.append(chunk)
        
            return b''.join(chunks)
        
class Server
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

    def __init__(self, host : str, port : int):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        
    def listen(self):
        self.server_sckt.bind((self.host, self.port))
        self.server_sckt.listen()
        while True:
            client_sock, addr = sock.accept()
            conn = ServerConnection(client_sock)
            Thread(target=conn).start()
            
        
