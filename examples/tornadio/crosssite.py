import sioclient

s = sioclient.SocketIO('localhost',8002)
s.send('hello from bot')
s.disconnect()
s.wait()
