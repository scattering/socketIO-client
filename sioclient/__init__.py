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
    def on(self, message, callback):
        setattr(self, "on_"+message.replace(" ","_"), callback)

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

    def on_message(self, msgid, msg):
        """
        Called when a message is received.  JSON messages will already
        be decoded when this is called.  Event signals will not signal
        a recv message.
        """
        print "unhandled message",msg

    def unknown_event(self, name, *args):
        """
        Called when there is no handler for a particular event.

        The event name will already be converted to on_name, with spaces
        in name converted to underscores.
        """
        print "unknown event %s(%s)"%(name,", ".join("%r"%s for s in args))

DEFAULT_HANDLER = Handler()
PROTOCOL = 1

class SocketIO(object):
    """
    SocketIO client connection.
    """
    def __init__(self, host, port, handler=None):
        self.host = host
        self.port = int(port)
        self.__do_handshake()
        self.__connect()
        self.heartbeatThread = RhythmicThread(self.heartbeatTimeout - 2, 
                                              self.__send_heartbeat)
        self.heartbeatThread.start()
        self.handler = handler
        self.special_handlers = {}
        self.channels = {}
        self.listenerThread = ListenerThread(self)
        self.listenerThread.start()
        self.msgid = 0

    def on(self, event, callback):
        self.special_handlers[event] = callback

    def get_handler(self, channel, event):
        if channel:
            source = self.channels[channel]
        else:
            source = self

        if event in source.special_handlers:
            return source.special_handlers[event]

        if source.handler is None:
            handler = DEFAULT_HANDLER
        else:
            handler = source.handler

        name = 'on_'+event.replace(' ','_')
        if hasattr(handler, name):
            return getattr(handler, name)
        else:
            return lambda *args: handler.unknown_event(name, *args)
    
    def __do_handshake(self):
        try:
            response = urlopen('http://%s:%d/socket.io/%s/' % (self.host, self.port,PROTOCOL))
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
        self.connection = create_connection('ws://%s:%d/socket.io/%s/websocket/%s' % (self.host, self.port, PROTOCOL, self.sessionID))

    def __del__(self):
        try:
            self.heartbeatThread.cancel()
            self.connection.close()
        except AttributeError:
            pass

    def __send_heartbeat(self):
        self.connection.send('2::')

    def disconnect(self, channel=None):
        """
        Close the socket, or close an individual channel to the socket if
        channel is specified.
        """
        self.connection.send('0::'+channel if channel else '0::')
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

    def emit(self, event, *args):
        """
        Signal an event on the server.
        """
        self._emit(event, args, '')
    def _emit(self, event, args, channel):
        msgid = ''
        if len(args) > 1 and callable(args[-1]):
            args, callback = args[:-1], args[-1]
            self.msgid += 1
            msgid = str(self.msgid)+"+"
            self.listenerThread.callbacks[msgid] = callback
         
        msg = json.dumps(dict(name=event, args=args))
        #print "sending",msg
        self.connection.send(':'.join(('5',msgid,channel,msg)))

    def send(self, msg, callback=None):
        """
        Send a messge to the socketIO server.
        """
        self._send(msg, '', callback)

    def _send(self, msg, channel, callback):
        if isinstance(msg, basestring):
            code = '3'
            data = msg
        else:
            code = '4'
            data = json.dumps(msg)
        msgid = ''
        if callback is not None:
            self.msgid += 1
            msgid = str(self.msgid)+'+'
            self.listenerThread.callbacks[msgid] = callback
        self.connection.send(':'.join((code,msgid,channel,data)))

    def wait(self):
        """
        Wait for the event handler to terminate.
        """
        self.listenerThread.wait()
        self.listenerThread.join()

class Channel(object):
    """
    socket.IO channel connection.  The methods are similar to the methods
    in the main socket, but they only operate on a single channel.
    """
    def __init__(self, socket, channel, handler):
        self.socket = socket
        self.channel = channel
        self.handler = handler
        self.special_handlers = {}
    def disconnect(self):
        self.socket.disconnect(channel=self.channel)
    def emit(self, event, *args):
        self.socket._emit(event, args, channel=self.channel)
    def send(self, msg, callback=None):
        self.socket._send(msg, channel=self.channel, callback=callback)
    def on(self, event, callback):
        self.special_handlers[event] = callback

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
        self.callbacks = {}
        self.waiting = False

    def cancel(self):
        """Cancel the listener thread"""
        self.done.set()

    def wait(self):
        if len(self.callbacks) == 0:
            self.done.set()
        self.waiting = True

    def run(self):
        """Run the listener thread"""
        while not self.done.is_set():
            msg = self.socket.connection.recv()
            #print "recv",msg
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
        handler = self.socket.get_handler(channel,'error')
        handler(reason, advice)

    def connect(self, channel):
        """Notify handler that the connection is available"""
        handler = self.socket.get_handler(channel, 'connect')
        handler(self.socket)

    def disconnect(self, channel):
        """Notify hander that the connection has terminated"""
        handler = self.socket.get_handler(channel, 'disconnect')
        handler()

    def event(self, msgid, channel, data):
        """Signal an event in the handler"""
        event = json.loads(data)
        handler = self.socket.get_handler(channel, event['name'])
        handler(*event['args'])

    def recv(self, msgid, channel, data):
        """Receive a message or a json message"""
        #print "recv",msgid, channel, data
        handler = self.socket.get_handler(channel, 'message')
        handler(data)

    def ack(self, data):
        """Receive acknowledgement for an event"""
        parts = data.split('+',1)
        msgid = parts[0]+'+'
        args = json.loads(parts[1]) if len(parts)>1 else []
        callback = self.callbacks.get(msgid, None)
        if callback is None:
            handler = self.socket.get_handler('', 'error')
            handler('callback missing',
                    'could not find callback for message %r'%msgid)
        else:
            del self.callbacks[msgid]
            callback(*args)

            # allow termination when all results are in
            if self.waiting and len(self.callbacks) == 0:
                self.cancel()
    
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
