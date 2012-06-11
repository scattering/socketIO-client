import json
from threading import Thread, Event
from urllib import urlopen, urlencode
from websocket import create_connection


class SocketIO(object):

    def __init__(self, host, port):
        self.host = host
        self.port = int(port)
        self.__do_handshake()
        self.__connect()
        self.heartbeatThread = RhythmicThread(self.heartbeatTimeout - 2, self.__send_heartbeat)
        self.heartbeatThread.start()

    def __do_handshake(self):
        try:
            response = urlopen('http://%s:%d/socket.io/1/' % (self.host, self.port))
        except IOError:
            raise SocketIOError('Could not start connection')
        if 200 != response.getcode():
            raise SocketIOError('Could not establish connection')
        self.sessionID, heartbeatTimeout, connectionTimeout, supportedTransports = response.readline().split(':')
        self.heartbeatTimeout = int(heartbeatTimeout)
        self.connectionTimeout = int(connectionTimeout)
        if 'websocket' not in supportedTransports.split(','):
            raise SocketIOError('Could not parse handshake')

    def __connect(self):
        self.connection = create_connection('ws://%s:%d/socket.io/1/websocket/%s' % (self.host, self.port, self.sessionID))

    def __del__(self):
        try:
            self.heartbeatThread.cancel()
            self.connection.close()
        except AttributeError:
            pass

    def __send_heartbeat(self):
        self.connection.send('2')

    def emit(self, eventName, *args, **kw):
        """
        Signal an event
        """
        channel = kw.pop("channel","")
        id = kw.pop("id","")
        if kw:
            raise TypeError("Unknown keyword(s) "+", ".join(kw.keys()))
        msg = json.dumps(dict(name=eventName, args=args))
        #print "sending",msg
        self.connection.send(':'.join(('5',id,channel,msg)))

    def disconnect(self, channel=None):
        self.connection.send('0::'+channel if channel else '0::')
        if not channel: 
            self.heartbeatThread.cancel()
            self.connection.close()
    def connect(self, channel, query=None):
        self.connection.send('1::'+channel+('?'+urlencode(query) if query else ""))
        return Channel(self, channel)
    def send(self, msg, id="", channel=None):
        if isinstance(msg, basestring):
            code = '3'
            data = msg
        else:
            code = '4'
            data = json.dumps(msg)
        self.connection.send(':'.join((code,id,channel,data)))

class Channel(object):
    def __init__(self, socket, channel):
        self.socket = socket
        self.channel = channel
    def disconnect(self):
        self.socket.disconnect(channel=self.channel)
    def emit(self, eventName, *args, **kw):
        self.socket.emit(eventName, *args, channel=self.channel)
    def send(self, msg):
        self.socket.send(msg, channel=self.channel)

class SocketIOError(Exception):
    pass


class RhythmicThread(Thread):
    'Execute function every few seconds'

    daemon = True

    def __init__(self, intervalInSeconds, function, *args, **kw):
        super(RhythmicThread, self).__init__()
        self.intervalInSeconds = intervalInSeconds
        self.function = function
        self.args = args
        self.kw = kw
        self.done = Event()

    def cancel(self):
        self.done.set()

    def run(self):
        self.done.wait(self.intervalInSeconds)
        while not self.done.is_set():
            self.function(*self.args, **self.kw)
            self.done.wait(self.intervalInSeconds)
