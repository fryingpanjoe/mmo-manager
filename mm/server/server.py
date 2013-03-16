import socket
import select

from mm.common.networking import Channel


class Client(object):
    def __init__(self, client_id, channel):
        self.client_id = client_id
        self.channel = channel

    def write_event(self, event):
        self.channel.write_event(event)


class Server(object):
    def __init__(self, port):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('', port))
        self.server_socket.listen(5)
        self.client_sockets = []
        self.channels = {}

    def accept_pending_clients(self):
        if select.select([self.server_socket], [], [], 0)[0]:
            client_socket, address = self.server_socket.accept()
            self.client_sockets.append(client_socket)
            channel = Channel(client_socket)
            self.channels[client_socket] = channel
            return channel
        else:
            return None

    def broadcast_event(self, event):
        for channel in self.channels:
            channel.send_event(event)

    def read_from_clients(self):
        readable_sockets = select.select([self.client_sockets], [], [], 0)[0]
        for sock in readable_sockets:
            event = self.channels[sock].receive_event()
