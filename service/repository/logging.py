import threading
import sys
from service.repository.repository import Repository
from service.model.message import Message


class SingletonMeta(type):
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

class Logger(metaclass=SingletonMeta):
    """ Singleton class providing an interface to log data in different ways.

    Attributes
    ----------
    repositories : List[Repository]
       List of objects that implement the append(d : DataModel) method 

    Methods
    -------
    append( d : DataModel) -> None
       Forwarded to the repository in the list.

    add_repository( r : Repository )
       Adds a repository to the list
    remove_repository( r : Repository )
       Removes from list

    Static Methods for construction
    -------------------------------
    screen_logger() -> Logger
       A logger that dumps to stdout
    cvs_logger(filename : str) -> Logger
       A logger that appends to a file.
    sqlite_logger(dbfilename : str) -> Logger
       A logger that writes to an sqlite database file
   
    """

    def __init__(self):

        self.repositories = []
        self.lock = threading.Lock()
        
    def append(self, d : Message):
        with self.lock:
            [r.append(d) for r in self.repositories]

    def add_repository(self, r : Repository):
        with self.lock:
            self.repositories.append(r)

    def remove_repository (self, r : Repository):
        with self.lock:
            try:
                self.repositories.remove(r)
            except ValueError:
                #Not present
                pass
            

    def add_screen(self, file=sys.stdout):
        logger = Logger()
        logger.add_repository(Repository.screen_repository(file))
        return logger

    def add_csv_repository(self, filename : str):
        logger = Logger()
        logger.add_repository(Repository.csv_repository(filename))
        return logger
        
    


