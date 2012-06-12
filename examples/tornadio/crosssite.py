import time
import sioclient

s = sioclient.SocketIO('localhost',8002)
s.send('hello from bot')
time.sleep(1)
s.disconnect()
time.sleep(1)
