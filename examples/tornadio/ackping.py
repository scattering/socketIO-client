import time
import math

from sioclient import SocketIO, Handler

def client_date():
    now = time.time()
    ms = int(1000 * (now - math.floor(now)))
    s = time.localtime(now)
    return [s.tm_hour, s.tm_min, s.tm_sec, ms]

def handle_ping(client, server):
    print "client %02d:%02d:%02d.%03d"%tuple(client)
    print "server %02d:%02d:%02d.%03d"%tuple(server)

s = SocketIO('localhost',8001, handler=Handler())
s.emit('ping', client_date(), handle_ping)
time.sleep(1)
s.emit('ping', client_date(), handle_ping)
time.sleep(1)
s.emit('ping', client_date(), handle_ping)
time.sleep(1)
s.emit('ping', client_date(), handle_ping)
s.wait()
