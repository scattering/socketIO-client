import time
import sioclient
import websocket
#websocket.enableTrace(True)

def printfn(*args): print " ".join(str(xi) for xi in args)

s = sioclient.SocketIO('localhost',8001)
s.on('response', lambda x: printfn(x))
s.emit('query',1)
s.emit('query',2)
s.emit('query',3)
time.sleep(10)
