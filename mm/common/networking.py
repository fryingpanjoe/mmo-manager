import logging
import socket
import select
import struct

from mm.common.events import (serialize_event_to_string,
                              serialize_event_from_string,
                              ClientConnectedEvent,
                              ClientDisconnectedEvent)

LOG = logging.getLogger(__name__)

DEFAULT_NETWORK_PORT = 8888


class WriteBuffer(object):
    def __init__(self, max_size=None):
        self.buffer = ''
        self.max_size = max_size

    def get_buffer_data(self):
        return self.buffer

    def get_buffer_size(self):
        return len(self.buffer)

    def is_empty(self):
        return len(self.buffer) == 0

    def can_write(self, length=1):
        if self.max_size is None:
            return True
        else:
            return len(self.buffer) + length <= self.max_size

    def skip(self, length):
        if len(self.buffer) >= length:
            self.buffer = self.buffer[length:]
        else:
            raise RuntimeError(
                'Not enough data in buffer to skip %d bytes' % (length,))

    def write(self, data):
        if self.can_write(len(data)):
            self.buffer += data
            return True
        else:
            return False

    def write_string(self, data):
        return (self.can_write(2 + len(data)) and
                self.write_uint16(len(data)) and
                self.write(data))

    def write_int16(self, data):
        return self.can_write(2) and self.write(struct.pack('!h', data))

    def write_uint16(self, data):
        return self.can_write(2) and self.write(struct.pack('!H', data))

    def write_int32(self, data):
        return self.can_write(4) and self.write(struct.pack('!i', data))

    def write_uint32(self, data):
        return self.can_write(4) and self.write(struct.pack('!I', data))

    def write_float(self, data):
        return self.can_write(4) and self.write(struct.pack('!f', data))


class ReadBuffer(object):
    def __init__(self, buf=None):
        if buf:
            self.buffer = buf
        else:
            self.buffer = ''

    def get_buffer_data(self):
        return self.buffer

    def get_buffer_size(self):
        return len(self.buffer)

    def feed(self, data):
        self.buffer += data

    def peek(self, length):
        if self.can_read(length):
            return self.buffer[:length]
        else:
            return None

    def can_read(self, length=1):
        return len(self.buffer) >= length

    def skip(self, length):
        if self.can_read(length):
            self.buffer = self.buffer[length:]

    def read(self, length):
        if len(self.buffer) >= length:
            data = self.buffer[:length]
            self.buffer = self.buffer[length:]
            return data
        else:
            return None

    def read_string(self):
        length = struct.pack('!H', self.peek(2))
        if self.can_read(2 + length):
            self.skip(2)
            return self.read(length)
        else:
            return None

    def read_int16(self):
        data = self.read(2)
        if data:
            data = struct.pack('!h', data)
        return data

    def read_uint16(self):
        data = self.read(2)
        if data:
            data = struct.pack('!H', data)
        return data

    def read_int32(self):
        data = self.read(4)
        if data:
            data = struct.pack('!i', data)
        return data

    def read_uint32(self):
        data = self.read(2)
        if data:
            data = struct.pack('!I', data)
        return data


class Channel(object):
    MAX_MESSAGE_SIZE = 4096
    MAX_RECEIVE_SIZE = 4096

    def __init__(self, sock):
        self.sock = sock

        # in- and outbound buffers
        self.write_buffer = WriteBuffer()
        self.read_buffer = ReadBuffer()

        # keep track of last sent message id
        self.send_message_id = 0

        # keep track of last received message id
        self.recv_message_id = None

        # in- and outbound event queues
        self.in_events = []
        self.out_events = []

    def synchronize(self):
        if self.receive_data():
            self.send_data()
            return True
        else:
            return False

    def receive_data(self):
        # check if there's anything on the socket
        readable, _, _ = select.select([self.sock], [], [])
        if readable:
            # read data!
            data = self.sock.recv(self.MAX_RECEIVE_SIZE)

            if not data:
                # client disconnected
                return False

            # handle recevied data
            self.read_buffer.feed(data)
            self.on_data_received()

        return True

    def send_data(self):
        # serialize any outbound events in queue
        if self.out_events:
            event_writer = WriteBuffer(self.MAX_MESSAGE_SIZE)

            # serialize as many events as possible
            while self.out_events:
                event = self.out_events[0]
                serialized_event = serialize_event_to_string(event)
                if event_writer.can_write(len(serialized_event)):
                    event_writer.write_string(serialized_event)
                    self.out_events.pop(0)
                else:
                    break

            # write message header and data
            self.write_buffer.write_int32(self.send_message_id)
            self.write_buffer.write_string(event_writer.get_buffer_data())

            # ready for next message
            self.send_message_id += 1

        # check if we have anything to send, and try to send it
        if not self.write_buffer.is_empty():
            # check if the socket is writable
            _, writable, _ = select.select([], [self.sock], [], 0)
            if writable:
                # send data!
                bytes_sent = self.sock.send(self.write_buffer.get_buffer_data())
                self.write_buffer.skip(bytes_sent)

    def on_data_received(self):
        # read message id
        if not self.recv_message_id:
            message_id = self.read_buffer.read_int32()
            if message_id:
                if (self.recv_message_id + 1) != message_id:
                    raise RuntimeError(
                        'Out of sync %d + 1 != %d' %
                        (self.recv_message_id, message_id))
                self.recv_message_id = message_id

        # read message data
        if self.recv_message_id:
            message_data = self.read_buffer.read_string()
            if message_data:
                self.on_message_received(message_data)

    def on_message_received(self, message_data):
        event_reader = ReadBuffer(message_data)
        while event_reader.can_read():
            serialized_event = event_reader.read_string()
            if serialized_event:
                self.in_events.append(
                    serialize_event_from_string(serialized_event))
            else:
                # no more events
                break

        if event_reader.can_read():
            LOG.warning(
                '%d bytes of unparsed message data' %
                (event_reader.get_buffer_size(),))

        # ready for next message
        self.recv_message_id = None

    def send_event(self, event):
        self.out_events.append(event)

    def receive_events(self):
        for event in self.in_events:
            yield self.in_events

        # clear inbound queue
        self.in_events = []


class Client(object):
    def __init__(self, event_distributor):
        self.event_distributor = event_distributor
        self.server_socket = None
        self.channel = None

    def is_connected(self):
        return self.server_socket

    def connect(self, address, port):
        LOG.info('Connecting to server %s:%d', address, port)
        self.server_socket = socket.create_connection((address, port))
        self.server_socket.setblocking(False)
        self.channel = Channel(self.server_socket)

    def disconnect(self):
        LOG.info('Disconnecting from server')
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
            LOG.info('Server closed the connection')
            self.disconnect()
            self.event_distributor.post(ClientDisconnectedEvent(0))


class Server(object):
    def __init__(self, event_distributor, port):
        self.event_distributor = event_distributor
        self.port = port
        self.server_socket = None
        self.client_sockets = []
        self.channels = {}

    def start_server(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.setblocking(0)
        self.server_socket.bind(('', self.port))
        self.server_socket.listen(10)

    def stop_server(self):
        self.server_socket.close()

    def accept_pending_clients(self):
        readable, _, _ = select.select([self.server_socket], [], [], 0)
        if readable:
            client_socket, address = self.server_socket.accept()
            client_socket.setblocking(0)
            self.client_sockets.append(client_socket)
            client_id = client_socket.fileno()
            self.channels[client_id] = Channel(client_socket)
            self.event_distributor.post(ClientConnectedEvent(client_id))
            LOG.info('Client %d connected', client_id)

    def broadcast_event(self, event):
        for channel in self.channels.itervalues():
            channel.send_event(event)

    def send_event(self, client_id, event):
        self.channels[client_id].send_event(event)

    def read_from_clients(self):
        readable, _, _ = select.select(self.client_sockets, [], [], 0)
        for sock in readable:
            client_id = sock.fileno()
            channel = self.channels[client_id]
            if channel.receive_data():
                for event in channel.receive_events():
                    self.event_distributor.post(ClientEvent(client_id, event))
            else:
                LOG.info('Client %d disconnected', client_id)
                self.client_sockets.remove(sock)
                del self.channels[client_id]
                self.event_distributor.post(
                    ClientDisconnectedEvent(client_id))

    def write_to_clients(self):
        _, writable, _ = select.select([], self.client_sockets, [], 0)
        for sock in writable:
            client_id = sock.fileno()
            self.channels[client_id].send_data()
