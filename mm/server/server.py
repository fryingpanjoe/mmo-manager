import logging
import socket
import select

from mm.common.events import *
from mm.common.networking import Channel, GAME_NETWORK_PORT

LOG = logging.getLogger(__name__)


class Server(object):
    def __init__(self, event_distributor):
        self.event_distributor = event_distributor
        self.server_socket = None
        self.client_sockets = []
        self.channels = {}

    def start_server(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.setblocking(False)
        self.server_socket.bind(('', GAME_NETWORK_PORT))
        self.server_socket.listen(5)

    def stop_server(self):
        self.server_socket.close()

    def accept_pending_clients(self):
        readable, _, _ = select.select([self.server_socket], [], [], 0)
        if readable:
            client_socket, address = self.server_socket.accept()
            client_socket.setblocking(False)
            self.client_sockets.append(client_socket)
            client_id = client_socket.fileno()
            self.channels[client_id] = Channel(client_socket)
            self.event_distributor.post(ClientConnectedEvent(client_id))
            LOG.info('Client %d connected', client_id)
            LOG.info('Channels: %s', self.channels)

    def broadcast_event(self, event):
        for channel in self.channels.itervalues():
            channel.send_event(event)

    def send_event(self, client_id, event):
        LOG.info('Channels: %s', self.channels)
        self.channels[client_id].send_event(event)

    def read_from_clients(self):
        readable, _, _ = select.select(self.client_sockets, [], [], 0)
        for sock in readable:
            client_id = sock.fileno()
            if self.channels[client_id].receive_data():
                for event in self.channels[sock].receive_events():
                    self.event_distributor.post(ClientEvent(client_id, event))
            else:
                self.client_sockets.remove(sock)
                del self.channels[client_id]
                self.event_distributor.post(
                    ClientDisconnectedEvent(client_id))

    def write_to_clients(self):
        _, writable, _ = select.select([], self.client_sockets, [], 0)
        for sock in writable:
            client_id = sock.fileno()
            self.channels[client_id].send_data()
