import time
import math

import sioclient

def client_date():
    now = time.time()
    ms = int(1000 * (now - math.floor(now)))
    s = time.localtime(now)
    return [s.tm_hour, s.tm_min, s.tm_sec, ms]

def handle_ping(data):
    print "client %02d:%02d:%02d.%03d"%tuple(data['client'])
    print "server %02d:%02d:%02d.%03d"%tuple(data['server'])

def printfn(*args): print " ".join(str(s)  for s in args)

s = sioclient.SocketIO('localhost',8001)
chat = s.connect('/chat')
chat.on('message', printfn)
ping = s.connect('/ping')
ping.on('message', handle_ping)
ping.send({'client': client_date()})
chat.send('hello, buddy')
time.sleep(1)
ping.send({'client': client_date()})
chat.send('goodbye')
time.sleep(1)
s.wait()
