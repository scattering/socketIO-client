import time
import sioclient
import websocket
websocket.enableTrace(True)

s = sioclient.SocketIO('localhost',8001)
s.emit('query',1)
s.emit('query',2)
s.emit('query',3)
time.sleep(10)
