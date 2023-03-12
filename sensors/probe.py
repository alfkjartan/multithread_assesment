import psutil

def cpu_utilization():
    return psutil.cpu_percent()

def load_average():
    la,_,_ = psutil.getloadavg()
    return la

def memory_available():
    mem = psutil.virtual_memory()
    return mem.available*1e-9 # Convert to Gb

def cpu_temp():
    temps = psutil.sensors_temperatures()
    if temps == {}:
        return -1
    key, val = next(iter( temps.items() )) # Just guessing that the first is the interesting one.
    return val[0].current
    
