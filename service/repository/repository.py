import sys
import abc
import numpy as np
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

    Changed to use Composite pattern.
    
    Repository objects are list-like, so they implement `append` and are iterable. 
    
    """

    def __init__(self):
        self.repositories = []
        
    def append(self, message: Message):
        for r in self.repositories:
            r.append(message)

    def __iter__(self):
        # The objects themselves are iterable
        return chain(*self.repositories)

    def __next__(self):
        """Must be overridden by subclasses that actually iterates"""
        raise StopIteration()

    def add_repository(self, r):
        self.repositories.append(r)
        
    # Factory methods
    def screen_dump(self, where=sys.stdout):
        self.repositories.append(ScreenRepository(where))
        return self

    def csv(self, filename : str):
        self.repositories.append(CSVRepository(filename))
        return self

    def sql(self, filename : str):
        self.repositories.append(SQLRepository(filename))
        return self

    def plot(self,num_sensors : int):
        self.repositories.append(PlotRepository(num_sensors))
        return self

class ScreenRepository(Repository):

    def __init__(self, where=sys.stdout):
        self.file = where


    def append(self, message : Message):
        print("\t".join(map(str, message.__dict__.values())), file=self.file)


class CSVRepository(Repository):
    """ Repository that saves messages to csv file.

    Tests
    ----
    >>> fname = '/tmp/csvtest.csv'
    >>> rep = CSVRepository(fname)
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
    
    def __init__(self, filename : str):
        self.filename = filename
        self.q = qmod.Queue()
        self.stop_event = mt.Event()
        self.worker_thread = mt.Thread(target=CSVRepository.write,
                                       args=(filename, self.q, self.stop_event))
        self.worker_thread.start()
        
    def append(self, message : Message):
        if message.data is None:
            # This is a flag raied by the sensor process that it is closing down.
            self.stop_event.set()
            return
        self.q.put(message)

    def write(filename : str, q : qmod.Queue, stop_event : mt.Event):
        header_written = False
        while True:
            if stop_event.is_set():
                break

            try:
                message = q.get(timeout=0.01)
            except qmod.Empty:
                continue

            if not header_written:
                with open(filename, 'w') as f:
                    f.write(", ".join(map(str, message.__dict__.keys())))
                    f.write("\n")
                    header_written = True
            with open(filename, 'a') as f:
                f.write(", ".join(map(str, message.__dict__.values())))
                f.write("\n")

    def __iter__(self):
        print("Iterating over data in {}".format(self.filename))
        self.file_to_read = open(self.filename, 'r+')
        # Read the first line to get the headings = attributes.
        self.headers = [s.strip() for s in self.file_to_read.readline().split(',')]
        return self
        
    def __next__(self):
        line = self.file_to_read.readline()
        if line == '':
            raise StopIteration
        
        vals = [s.strip() for s in line.split(',')]
        message = Message.message()
        message.from_list(vals)

        return message
    
        
class SQLRepository(Repository):
    """
    Creates (if needed) and saves data to an SQLite database on file. 

    """

    def __init__(self,  filename : str, cache_size = 21):
        self.filename = filename
        self.lock = mt.Lock()
        self.table = "sensor_messages"
        self.initial_db = 'message_id INTEGER PRIMARY KEY'
        self.cache = []
        self.cache_size = cache_size
        self.table_created = False
        self.rowid = 0

    def append(self, message : Message):
        if not self.table_created:
            with self.lock:
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
                self.table_created = True
            
        if len(self.cache) < self.cache_size:
            self.cache.append([self.rowid] + list(message.__dict__.values()))
            self.rowid += 1
        else:
            # Write cached messages to db
            self._flush()

    def _flush(self):
        with self.lock:
            with sqlite3.connect(self.filename) as con:
                cur = con.cursor()
                cur.executemany('INSERT INTO {} VALUES (?, ?, ?, ?, ?)'.format(self.table), self.cache)
                self.cache.clear()
                    
    def to_sql_string(v : Any) -> str:
        """Returns the sql type as a string corresponding to the datatype of the argument.
        Supports only a 
        """
        if isinstance(v, str): return "TEXT"
        if isinstance(v, int): return "INTEGER"
        if isinstance(v, float): return "REAL"

        raise NotImplemented("Only types str, int and float supported")

    def __iter__(self):
        print("Iterating over data in {}".format(self.table))
        self.rowid = 1
        return self

    def __next__(self):
        with self.lock:
            with sqlite3.connect(self.filename) as con:
                cur = con.cursor()
                res = cur.execute('SELECT * FROM {} WHERE rowid = {}'.format(self.table, self.rowid))
                row = res.fetchall()
                if len(row) == 0:
                    raise StopIteration
                else:
                    self.rowid += 1
                    return row

    
class PlotRepository(Repository):
    """
    Creates a figure and plots data as they arrive.

    Due to a restriction that Matplotlib figures in TKinter can only run in the main
    loop, a separate process is spawn for the plot.
    """

    def __init__(self, num_sensors : int, figsize=(14,10)):
        self.stop_event = mp.Event()
        self.message_queue = mp.Queue()
        self.plot_proc = mp.Process(target=PlotRepositoryBackend.run,
                                 args=[self.stop_event, self.message_queue, num_sensors, figsize])
        self.plot_proc.start()
        
    def append(self, message : Message):
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
    
