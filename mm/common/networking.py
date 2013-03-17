import logging
import socket
import select
import struct
import zlib

from mm.common.events import (serialize_event_to_string,
                              serialize_event_from_string,
                              ClientConnectedEvent,
                              ClientDisconnectedEvent,
                              ClientEvent)

LOG = logging.getLogger(__name__)

DEFAULT_NETWORK_PORT = 8888
COMPRESSION_LEVEL = 1


def compress_data(data):
    return zlib.compress(data, COMPRESSION_LEVEL)


def decompress_data(data):
    return zlib.decompress(data)



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
        length = struct.unpack('!H', self.peek(2))[0]
        if self.can_read(2 + length):
            self.skip(2)
            return self.read(length)
        else:
            return None

    def read_int16(self):
        data = self.read(2)
        if data:
            data = struct.unpack('!h', data)[0]
        return data

    def read_uint16(self):
        data = self.read(2)
        if data:
            data = struct.unpack('!H', data)[0]
        return data

    def read_int32(self):
        data = self.read(4)
        if data:
            data = struct.unpack('!i', data)[0]
        return data

    def read_uint32(self):
        data = self.read(2)
        if data:
            data = struct.unpack('!I', data)[0]
        return data


class Channel(object):
    MAX_MESSAGE_SIZE = 8192
    MAX_RECEIVE_SIZE = 8192

    def __init__(self, sock):
        self.sock = sock

        # in- and outbound buffers
        self.write_buffer = WriteBuffer()
        self.read_buffer = ReadBuffer()

        # keep track of last sent message id
        self.send_message_id = 1

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
        try:
            # check if there's anything on the socket
            readable, _, _ = select.select([self.sock], [], [], 0)
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
        except socket.error:
            LOG.exception('Socket error')
            return False

    def send_message(self, message_data):
        compressed_message_data = compress_data(message_data)

        LOG.debug(
            'Compression %d -> %d bytes, compression factor %f',
            len(message_data), len(compressed_message_data),
            float(len(compressed_message_data)) / len(message_data))

        self.write_buffer.write_int32(self.send_message_id)
        self.write_buffer.write_string(compressed_message_data)

        self.send_message_id += 1

    def send_all_events(self):
        message_writer = None

        for event in self.out_events:
            LOG.info('writing event %s', type(event))
            if not message_writer:
                message_writer = WriteBuffer(self.MAX_MESSAGE_SIZE)

            # serialize event to string
            serialized_event = serialize_event_to_string(event)

            if not message_writer.write_string(serialized_event):
                if len(serialized_event) > self.MAX_MESSAGE_SIZE:
                    # event will never fit in a message
                    raise RuntimeError(
                        'Event size %d too big' % (len(serialized_event),))
                else:
                    # send message and continue with the next
                    self.send_message(message_writer.get_buffer_data())
                    message_writer = None

        # no outbound events left
        self.out_events = []

    def send_data(self):
        try:
            # serialize and send all outbound events
            if self.out_events:
                self.send_all_events()

            # check if we have anything to send, and try to send it
            if not self.write_buffer.is_empty():
                # check if the socket is writable
                _, writable, _ = select.select([], [self.sock], [], 0)
                if writable:
                    # send data!
                    bytes_sent = self.sock.send(
                        self.write_buffer.get_buffer_data())

                    if bytes_sent == 0:
                        # something went wrong
                        return False

                    self.write_buffer.skip(bytes_sent)

            return True
        except socket.error:
            LOG.exception('Socket error')
            return False

    def on_data_received(self):
        # read message id
        if not self.recv_message_id:
            message_id = self.read_buffer.read_int32()
            if message_id:
                if (self.recv_message_id and
                    self.recv_message_id != (message_id - 1)):
                    raise RuntimeError(
                        'Out of sync %d + 1 != %d' %
                        (self.recv_message_id, message_id))
                self.recv_message_id = message_id

        # read message data
        if self.recv_message_id:
            message_data = self.read_buffer.read_string()
            if message_data:
                self.on_message_received(decompress_data(message_data))

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
            yield event

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
        if self.server_socket:
            self.channel = Channel(self.server_socket)
            return True
        else:
            LOG.info('Failed to connect to server %s:%d', address, port)
            return False

    def disconnect(self):
        LOG.info('Disconnecting from server')
        self.server_socket.close()
        self.server_socket = None
        self.channel = None

    def send_event(self, event):
        self.channel.send_event(event)

    def read_from_server(self):
        if self.channel.receive_data():
            for event in self.channel.receive_events():
                self.event_distributor.post(event)
        else:
            LOG.info('Server closed the connection')
            self.disconnect()
            self.event_distributor.post(ClientDisconnectedEvent(0))

    def write_to_server(self):
        if not self.channel.send_data():
            LOG.info('Broken socket, disconnecting')
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
        self.server_socket.bind(('', self.port))
        self.server_socket.listen(10)

    def stop_server(self):
        if self.server_socket:
            self.server_socket.close()
            self.server_socket = None

    def accept_pending_clients(self):
        readable, _, _ = select.select([self.server_socket], [], [], 0)
        if readable:
            client_socket, address = self.server_socket.accept()
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
            if not self.channels[client_id].send_data():
                LOG.info('Broken socket to client %d, disconnecting', client_id)
                self.client_sockets.remove(sock)
                del self.channels[client_id]
                self.event_distributor.post(
                    ClientDisconnectedEvent(client_id))
