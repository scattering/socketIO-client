import json
from threading import Thread, Event
from urllib import urlopen, urlencode
from websocket import create_connection

class Handler(object):
    """
    SocketIO client handler.

    Subclass this method with "on_name" for each event "name"
    that you expect to receive from the server.  Spaces in
    event names will be converted to underscores.

    The event handler is run in a listener thread.
    """
    # Standard messages
    def on_connect(self, socket):
        """
        Called when the server connects.
        """

    def on_disconnect(self):
        """
        Called when the server disconnects.
        """

    def on_reconnect(self, *args):
        print "reconnect with",args

    def on_open(self,*args):
        print "open with",args

    def on_close(self,*args):
        print "close with",args

    def on_retry(self, *args):
        print "retry with",args

    def on_error(self, name, msg):
        """
        Called when there is an error.
        """
        print "error %s:"%name,msg

    def on_message(self, msg):
        """
        Called when a message is received.  JSON messages will already
        be decoded when this is called.  Event signals will not signal
        a recv message.
        """
        print "unhandled message",msg

    def unknown_event(self, name, args):
        """
        Called when there is no handler for a particular event.

        The event name will already be converted to on_name, with spaces
        in name converted to underscores.
        """
        print "unknown event",name,args

    def ack(self, msgid, event=None, args=[]):
        """
        Server sent an acknowledgement to message.  Ideally we should
        never see this since the acknowledgement should trigger the
        callback for a sent message, but that code hasn't been written yet.
        """
        print "ack",msgid

class SocketIO(object):
    """
    SocketIO client connection.
    """
    def __init__(self, host, port, handler=None):
        self.host = host
        self.port = int(port)
        self.__do_handshake()
        self.__connect()
        self.heartbeatThread = RhythmicThread(self.heartbeatTimeout - 2, self.__send_heartbeat)
        self.heartbeatThread.start()
        self.main_handler = handler
        self.channels = {}
        self.listenerThread = ListenerThread(self)
        self.listenerThread.start()

    def handler(self, channel):
        if channel:
            return self.channels[channel].handler
        else:
            return self.main_handler

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
        Signal an event on the server.

        If channel keyword is specified, the event will be emitted on a
        particular channel.
        """
        channel = kw.pop("channel","")
        msgid = kw.pop("msgid","")
        if kw:
            raise TypeError("Unknown keyword(s) "+", ".join(kw.keys()))
        msg = json.dumps(dict(name=eventName, args=args))
        #print "sending",msg
        self.connection.send(':'.join(('5',msgid,channel,msg)))

    def disconnect(self, channel=None):
        """
        Close the socket, or close an individual channel to the socket if
        channel is specified.
        """
        self.connection.send('0::'+channel if channel else '0')
        if channel:
            del self.channels[channel]
        if not channel: 
            self.heartbeatThread.cancel()
            self.listenerThread.cancel()
            self.connection.close()

    def connect(self, channel, handler=None, query=None):
        """
        Connect to a channel in the socketIO server.

        Returns a connection with emit/send methods for communicating with the
        server.
        """
        self.connection.send('1::'+channel+('?'+urlencode(query) if query else ""))
        self.channels[channel] = Channel(self, channel, handler)
        return self.channels[channel]

    def send(self, msg, msgid="", channel=None):
        """
        Send a messge to the socketIO server.
        """
        if isinstance(msg, basestring):
            code = '3'
            data = msg
        else:
            code = '4'
            data = json.dumps(msg)
        self.connection.send(':'.join((code,msgid,channel,data)))

    def wait(self):
        """
        Wait for the event handler to terminate.
        """
        self.listenerThread.join()

class Channel(object):
    """
    Connection for sending messges to the socketIO server on a particular channel.

    Note: does not yet support channel specific handlers.
    """
    def __init__(self, socket, channel, handler):
        self.socket = socket
        self.channel = channel
        self.handler = handler
    def disconnect(self):
        self.socket.disconnect(channel=self.channel)
    def emit(self, eventName, *args, **kw):
        self.socket.emit(eventName, *args, channel=self.channel)
    def send(self, msg):
        self.socket.send(msg, channel=self.channel)

class SocketIOError(Exception):
    pass

class ListenerThread(Thread):
    """
    Thread to process messages from the server.
    """
    daemon = True

    def __init__(self, socket):
        super(ListenerThread,self).__init__()
        self.done = Event()
        self.socket = socket

    def cancel(self):
        """Cancel the listener thread"""
        self.done.set()

    def run(self):
        """Run the listener thread"""
        while not self.done.is_set():
            msg = self.socket.connection.recv()
            if msg is None: break
            split_data = msg.split(":",3)
            if len(split_data) == 4:
                code, msgid, channel, data = split_data
            elif len(split_data) == 3:
                code, msgid, channel = split_data
                data = ''
            elif len(split_data) == 1:
                code = msg
                msgid = channel = data = ''
            else:
                raise ValueError("message could not be parsed:\n  "+msg)

            if code == '5':
                self.event(msgid, channel, data)
            elif code == '0':
                self.disconnect(channel)
            elif code == '1':
                self.connect(channel)
            elif code == '3':
                self.recv(msgid, channel, data)
            elif code == '4':
                self.recv(msgid, channel, json.loads(data))
            elif code == '6':
                self.ack(data)
            elif code == '7':
                self.error(channel, data)

    def error(self, channel, message):
        """Notify handler that an error occurred"""
        reason,advice = message.split('+',1)
        handler = self.socket.handler(channel)
        handler.on_error(reason, advice)

    def connect(self, channel):
        """Notify handler that the connection is available"""
        handler = self.socket.handler(channel)
        handler.on_connect(self.socket)

    def disconnect(self, channel):
        """Notify hander that the connection has terminated"""
        handler = self.socket.handler(channel)
        handler.on_disconnect()

    def event(self, msgid, channel, data):
        """Signal an event in the handler"""
        if msgid or channel:
            raise NotImplementedError("not yet supporting message ids and channels")
            # proper implementation should have callbacks associated with messages,
            # so that when the particular message is is returned, then the specific
            # callback is called.  We aren't there yet.
        event = json.loads(data)
        name = 'on_'+event['name'].replace(' ','_')
        #print "event",event
        handler = self.socket.handler(channel)
        if hasattr(handler, name):
            getattr(handler, name)(*event['args'])
        else:
            handler.unknown_event(name, event['args'])

    def recv(self, msgid, channel, data):
        """Receive a message or a json message"""
        handler = self.socket.handler(channel)
        handler.on_message(msgid, data)

    def ack(self, data):
        """Receive acknowledgement for an event"""
        plus_idx = data.find('+')
        if plus_idx > 0:
            msgid, event = data[:plus_idx],json.loads(data[plus_idx+1:])
            name = 'on_'+event['name'].replace(' ','_')
            args = event['args']
            self.socket.handler.ack(msgid, name, args)
        else:
            self.socket.handler.ack(msgid)

    
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
