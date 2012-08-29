[PAK, Aug 2012] Added channel support.  These changes have been pulled back into the original package
`https://github.com/invisibleroads/socketIO-client`_  This fork will not be maintained.

socketIO.client
===============
Here is a `socket.io <http://socket.io>`_ client library for Python.

Thanks to `rod <http://stackoverflow.com/users/370115/rod>`_ for his `StackOverflow question and answer <http://stackoverflow.com/questions/6692908/formatting-messages-to-send-to-socket-io-node-js-server-from-python-client/>`_, on which this code is based.

Thanks also to `liris <https://github.com/liris>`_ for his `websocket-client <https://github.com/liris/websocket-client>`_ and to `guille <https://github.com/guille>`_ for the `socket.io specification <https://github.com/LearnBoost/socket.io-spec>`_.


Installation
------------
::

    # Prepare isolated environment
    ENV=$HOME/Projects/env
    virtualenv $ENV 
    mkdir $ENV/opt

    # Activate isolated environment
    source $ENV/bin/activate

    # Install package
    easy_install -U socketIO-client


Usage
-----
::

    ENV=$HOME/Projects/env
    source $ENV/bin/activate
    python

        from sioclient import SocketIO
        s = SocketIO('localhost', 8000)
        s.emit('news', {'hello': 'world'})

Bidirectional Example
---------------------

The following chatbot connects to a socket.IO chat client, and complains
if it sees the string "bot".  See "chatbot.py" in the source distribution.

::

    class Handler(sioclient.Handler):
        def on_connect(self, socket):
            self.socket = socket
            self.socket.emit('nickname', 'bot')

        def on_msg_to_room(self, user, message):
            if "bot" in message and user != 'bot':
                self.socket.emit('user message', 'who are you calling bot?!')
            elif "bye" in message:
                self.socket.disconnect()

    
    server, port = sys.argv[1:3]
    s = sioclient.SocketIO(server, port, handler=Handler())
    s.wait()


The handler runs in a separate thread, listening for messages from the
socket.IO server.  The standard socket.IO events are supported::

    on_connect(self, socket)
    on_disconnect(self)
    on_error(self, name, message)
    on_message(self, id, message)

The following are also supported, but the arguments are not yet known::

    on_reconnect
    on_open
    on_close
    on_retry

Events signalled using socket.emit('NAME',['ARG1', 'ARG2', ...]) are received by::

    on_NAME(self, ARG1, ARG2, ...)

with spaces in NAME converted to underscores.  If on_NAME is not defined, then
the following is called instead::

    unknown_event(self, name, args)

Instead of using a handler class, you can instead add handlers directly
to the socket.  For example::

    socket.on('msg_to_room', 
              lambda who,what: who!='bot' or socket.emit('message', 'hi!'))

This isn't quite as handy as the javascript equivalent since lambdas in
python can only operate on a single expression.

Channels
--------

To open a channel, start with an open socket and connect to the specific 
channel.  For example, if you have handlers for main socket as well as a 
chat service and a key storing service, you can get the individual channel 
connections as follows::

    socket = sioclient.socketIO(server, port, MainHandler())
    chat = socket.connect("/chat", ChatHandler())
    keys = socket.connect("/keystore", KeyHanlder())

Messages emitted on the chat channel will be routed to the chat service, and
received by the chat handler.  For example::

    chat.emit('nickname', 'bot')
    chat.emit('user message', "I'm a bot")

Only one connection per channel is allowed for a socket.

RPC
---

If the last argument to an "emit" message is a callback, then the callback
will be called when the server replies.  The server will send a list of
arguments to supply to the callback.

