import sys
import numpy as np
from abc import ABCMeta, abstractmethod
import csv
from datetime import datetime
import multiprocessing as mp
import threading as mt
import queue as qmod
from itertools import chain
import matplotlib.pyplot as plt
import sqlite3
from typing import Any
from service.model.message import Message


class Repository():
    """ 
    Storage or visualization of incoming messages.
    Uses the Decorator pattern. See https://refactoring.guru/design-patterns/decorator
    
    Repository objects are list-like, so they implement `append` and are iterable. The 
    composition is obtained by maintaining references to other Repository objects in 
    a list. For the present use case, it is probably a very shallow tree of objects that
    will be in use.
    
    """

    def __init__(self):
        self.message_list = []
        
    def append(self, message: Message):
        self.message_list.append(message)

    def __iter__(self):
        return iter(self.message_list)

    def __next__(self):
        """Must be overridden by subclasses that handles the iteration themselves"""
        raise StopIteration()

        
    # Factory methods generating decorations.  These decorates the object with new behavior
    def screen_dump(self, where=sys.stdout):
        return ScreenRepository(where, self)

    def csv(self, filename : str):
        return CSVRepository(filename, self)

    def sql(self, filename : str):
        return SQLRepository(filename, self)

    def plot(self,num_sensors : int):
        return PlotRepository(num_sensors, self)

class RepositoryDecorator(Repository, metaclass=ABCMeta):
    """For common functionality of the different concrete decorator classes, including
    synchronization with a lock, and calling the decorated object's append() method.

    Subclasses must implement the _handle(message : Message) method.
    """

    def __init__(self, repository : Repository):
        self.repo = repository
        self.lock = mt.Lock()

    def append(self, message : Message):
        self.repo.append(message) # First let the decorated object do its work
        with self.lock:           # Then the decoration
            self._handle(message)

    @abstractmethod
    def _handle(self, message : Message):
        pass
    
class ScreenRepository(RepositoryDecorator):

    def __init__(self, repository : Repository, where=sys.stdout):
        super().__init__(repository)
        self.file = where


    def _handle(self, message : Message):
        print("\t".join(map(str, message.__dict__.values())), file=self.file)


class CSVRepository(RepositoryDecorator):
    """ Repository that saves messages to csv file.

    Tests
    ----
    >>> fname = '/tmp/csvtest.csv'
    >>> rep = Repository().csv(fname) 
    >>> msg = Message.message()
    >>> rep.append(msg)
    >>> for m in rep: 
    ...   m.id == msg.id 
    ...   m.name == msg.name 
    ...   m.data == msg.data 
    ...   m.time_stamp == msg.time_stamp 
    ... 
    True
    True
    True
    True
    """
    
    def __init__(self, filename : str, repository : Repository):
        super().__init__(repository)
        self.filename = filename
        self.header_written = False
        
    def _handle(self, message : Message):
        if message.data is None:
            return # Not saving None data, which is used as flag to stop logging.
        with open(self.filename, 'a', newline='') as csvfile:
            cw = csv.writer(csvfile)
            if not self.header_written:
                cw.writerow(list(message.__dict__.keys()))
                self.header_written = True
            cw.writerow(list(message.__dict__.values()))

    def __iter__(self):
        """Returns a list containing the rows of the whole file."""
        with open(self.filename, newline='') as csvfile:
            cr = csv.reader(csvfile)
            next(cr) # Skip the first line with headings
            rows = [Message.message_from_list(row) for row in cr]
            return iter(rows)
        
class SQLRepository(RepositoryDecorator):
    """
    Creates (if needed) and saves data to an SQLite database on file. 


    Tests
    ----
    >>> import uuid
    >>> fname = '/tmp/' + str(uuid.uuid4()) + '.db' # Unique filename 
    >>> rep = Repository().sql(fname)
    >>> msg = Message.message()
    >>> rep.append(msg)
    >>> for m in rep: 
    ...   m.id == msg.id 
    ...   m.name == msg.name 
    ...   m.data == msg.data 
    ...   m.time_stamp == msg.time_stamp 
    ... 
    True
    True
    True
    True
    """

    def __init__(self,  filename : str, repository : Repository):
        super().__init__(repository)
        self.filename = filename
        self.table = "sensor_messages"
        self.initial_db = 'message_id INTEGER PRIMARY KEY'
        self.table_created = False
        self.rowid = 0

    def _handle(self, message : Message):
        if message.data is None:
            return # Not saving None data, which is used as flag to stop logging.
        if not self.table_created:
            self._create_table(message)
            self.table_created = True
            
        with sqlite3.connect(self.filename) as con:
            cur = con.cursor()
            cur.execute('INSERT INTO {} VALUES (?, ?, ?, ?, ?)'.format(self.table),
                        [self.rowid] + list(message.__dict__.values()))
            cur.close()
            self.rowid += 1

                
    def _create_table(self, message):
        with sqlite3.connect(self.filename) as con:
            cur = con.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS {} ({})".format(self.table, self.initial_db))
            try:
                for k, v in message.__dict__.items():
                    sql = "ALTER TABLE {} ADD {} {}".format(self.table, k,
                                                            SQLRepository.to_sql_string(v))
                    
                    cur.execute(sql)
            except sqlite3.OperationalError:
                # Already defined the columns, so ignore error
                pass
            cur.close()

    def to_sql_string(v : Any) -> str:
        """Returns the sql type as a string corresponding to the datatype of the argument.
        Supports only a 
        """
        if isinstance(v, str): return "TEXT"
        if isinstance(v, int): return "INTEGER"
        if isinstance(v, float): return "REAL"

        raise NotImplemented("Only types str, int and float supported")

    def __iter__(self):
        self.rowid = 0
        return self

    def __next__(self):
        with sqlite3.connect(self.filename) as con:
            message = Message.message()
            cur = con.cursor()
            res = cur.execute('SELECT * FROM {} WHERE rowid = {}'.format(self.table, self.rowid))
            row = res.fetchall()
            if len(row) == 0:
                cur.close()
                raise StopIteration
            else:
                self.rowid += 1
                message.from_list(row[0][1:]) # The first element is the unique rowid no used in the message

                cur.close()
                return message
    
class PlotRepository(RepositoryDecorator):
    """
    Creates a figure and plots data as they arrive.

    Due to a restriction that Matplotlib figures in TKinter can only run in the main
    loop, a separate process is spawn for the plot.
    """

    def __init__(self, num_sensors : int, repository : Repository, figsize=(14,10)):
        super().__init__(repository)
        self.stop_event = mp.Event()
        self.message_queue = mp.Queue()
        self.plot_proc = mp.Process(target=PlotRepositoryBackend.run,
                                 args=[self.stop_event, self.message_queue, num_sensors, figsize])
        self.plot_proc.start()
        
    def _handle(self, message : Message):
        if message.data is None:
            # This is a flag raied by the sensor process that it is closing down.
            self.stop_event.set()
            return
        self.message_queue.put(message.to_json())

class PlotRepositoryBackend:
    """
    Creates a figure and plots data as they arrive.
    """

    def run(stop_event : mp.Event, queue : mp.Queue,  num_sensors : int, figsize=(14,10)):

        nrows = int(num_sensors/2) + num_sensors % 2
        ncols = 2
        if num_sensors == 1:
            ncols = 1
        plt.ion()
        fig, axs = plt.subplots(nrows=nrows, ncols=ncols, 
                                figsize=figsize, squeeze = False)
        plt.show()
        # So that in the case of a single axes, it also  becomes a list: 
        axs = list(chain.from_iterable(axs)) 
        start_times = [None]*num_sensors 
        lines = {}
        ymax = {}
        ymin = {}
        while True:
            if stop_event.is_set():
                break

            try:
                j_str = queue.get(timeout=0.01)
            except qmod.Empty:
                continue
            

            message = Message.from_json_str(j_str)
            
            ax = axs[message.id]
            if start_times[message.id] is None: # First message received from that sensor
                start_times[message.id] = datetime.fromisoformat(message.time_stamp)
                line, = ax.plot(0, message.data, 'bo')
                ax.set_title(message.name)
                ax.set_xlabel("Time [s]")
                lines[message.id] = line
                ymax[message.id] = _max(message.data)
                ymin[message.id] = ymax[message.id]
                
                
            start_t = start_times[message.id]
            t = (datetime.fromisoformat(message.time_stamp) - start_t).total_seconds()
            line = lines[message.id]
            line.set_xdata(np.append(line.get_xdata(), t))
            line.set_ydata(np.append(line.get_ydata(), message.data))

            # Adjust axes limits
            maxdata = _max(message.data)
            if maxdata > ymax[message.id]:
                ymax[message.id] = maxdata
                top_lim = 1.05*maxdata # Give some margin
            else:
                top_lim = None # Keep original limit
                
            mindata = _min(message.data)
            if mindata < ymin[message.id]:
                ymin[message.id] = mindata
                if mindata < 0:
                    bottom_lim = 1.05*mindata # Give some margin
                else:
                    bottom_lim = mindata - 0.05*maxdata  # Give some margin
            else:
                bottom_lim = None # Keep original limit

            ax.set_xlim(right=t+2)
            ax.set_ylim(bottom = bottom_lim, top=top_lim)
            fig.canvas.draw()
            fig.canvas.flush_events()
        
        print("Plot is closing down")
        
        
def _max(v):
    """ Version of regular max() function that handles scalars as well. """
    try:
        vm = max(v)
        return vm
    except TypeError:
        # Scalar data
        return v

def _min(v):
    """ Version of regular min() function that handles scalars as well. """
    try:
        vm = min(v)
        return vm
    except TypeError:
        # Scalar data
        return v
    
