import socket

from mm.common.networking import Channel


class Client(object):
    def __init__(self, event_distributor):
        self.event_distributor = event_distributor
        self.server_socket = None
        self.channel = None

    def is_connected(self):
        return self.server_socket

    def connect(self, address, port):
        self.server_socket = socket.create_connection((address, port))
        self.server_socket.setblocking(False)
        self.channel = Channel(self.server_socket)

    def disconnect(self):
        self.server_socket.close()
        self.server_socket = None
        self.channel = None

    def send_event(self, event):
        self.channel.send_event(event)

    def update(self):
        if self.channel.synchronize():
            for event in self.channel.receive_events():
                self.event_distributor.post(event)
        else:
            self.disconnect()
            self.event_distributor.post(ClientDisconnectedEvent(0))
