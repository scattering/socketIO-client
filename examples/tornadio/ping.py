import time
import math

from sioclient import SocketIO, Handler

def client_date():
    now = time.time()
    ms = int(1000 * (now - math.floor(now)))
    s = time.localtime(now)
    return [s.tm_hour, s.tm_min, s.tm_sec, ms]

s = SocketIO('localhost',8001, handler=Handler())
s.emit('ping',client_date(), msgid='1000+')
time.sleep(1)
s.disconnect()
time.sleep(1)
