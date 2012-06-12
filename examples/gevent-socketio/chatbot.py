#!/usr/bin/env python
"""
Client for the gevent-socketio examples chat.py socketIO server.

Responds to chat messages which contain the string "bot".

Stop the bot by sending a chat message with "bye" in the string.
"""
import sys
import time

import sioclient

class Handler(sioclient.Handler):
    def on_connect(self, socket):
        self.socket = socket
        self.socket.emit('nickname', 'bot')
        self.socket.emit('user message', 'hey, guys!')
    def on_msg_to_room(self, user, message):
        print user, ":", message
        if "bot" in message and user != 'bot':
            self.socket.emit('user message', 'who are you calling bot?!')
        elif "bye" in message:
            self.socket.disconnect()
    def on_announcement(self, message):
        print message
    def on_nicknames(self, names):
        print "nicknames",", ".join(names)

def demo():
    if len(sys.argv) != 3:
        sys.stderr.write('usage: python client.py <server> <port>\n')
        sys.exit(1)
    
    server = sys.argv[1]
    port = int(sys.argv[2])
    
    s = sioclient.SocketIO(server, port, handler=Handler())
    s.wait()

if __name__ == '__main__':
    demo()

