import sys
import abc
from datetime import datetime
import matplotlib.pyplot as plt
from multiprocessing import Process, Queue, Event
from queue import Empty
from itertools import chain
import numpy as np
from service.model.message import Message


class Repository(abc.ABC):
    """ 
    Storage or visualization of incoming messages.
    
    Repository objects are list-like, so they implement `append` and are iterable. 
    
    """
    @abc.abstractmethod
    def append(self, message: Message):
        pass

    def __iter__(self):
        # The objects themselves are iterable
        return self 

    def __next__(self):
        raise StopIteration()

    
    # Factory methods
    def screen_dump(where=sys.stdout):
        return ScreenRepository(where)

    def csv_repository(filename : str):
        return CSVRepository(filename)

    def plot(num_sensors : int):
        return PlotRepository(num_sensors)

class ScreenRepository(Repository):

    def __init__(self, where=sys.stdout):
        self.file = where


    def append(self, message : Message):
        print("\t".join(map(str, message.__dict__.values())), file=self.file)


class CSVRepository(Repository):

    def __init__(self, filename : str):
        self.filename = filename

        self.header_written = False
        
    def append(self, message : Message):
        if not self.header_written:
            with open(self.filename, 'w') as f:
                f.write(", ".join(map(str, message.__dict__.keys())))
                f.write("\n")
            self.header_written = True
        with open(self.filename, 'a') as f:
            f.write(", ".join(map(str, message.__dict__.values())))
            f.write("\n")

class PlotRepository(Repository):
    """
    Creates a figure and plots data as they arrive.

    Due to a restriction that Matplotlib figures in TKinter can only run in the main
    loop, a separate process is spawn for the plot.
    """

    def __init__(self, num_sensors : int, figsize=(10,10)):
        self.stop_event = Event()
        self.message_queue = Queue()
        self.plot_proc = Process(target=PlotRepositoryBackend.run,
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

    def run(stop_event : Event, queue : Queue,  num_sensors : int, figsize=(10,10)):

        nrows = int(num_sensors/2) + num_sensors % 2
        ncols = 2
        if num_sensors == 1:
            ncols = 1
        plt.ion()
        fig, axs = plt.subplots(nrows=nrows, ncols=ncols, 
                                figsize=figsize, squeeze = False)
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
            except Empty:
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
    
