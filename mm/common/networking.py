import socket
import struct
import StringIO

from mm.common.events import read_event, write_event


class Message(object):
    def __init__(self, message_id, events):
        self.message_id = message_id
        self.events = events

    def serialize_to_string(self):
        with StringIO.StringIO() as buf:
            buf.write(self.message_id)
            buf.write(len(self.events))
            for event in self.events:
                buf.write(write_event(event))
            return buf.getvalue()


class Channel(object):
    def __init__(self, sock):
        self.sock = sock
        self.read_buf = StringIO.StringIO()
        self.send_message_id = 0
        self.last_recv_message_id = 0

    def send_event(self, event):
        data = write_event(event)
        if len(data) > 65535:
            raise RuntimeError('event size too large: ' + len(data))
        self.send_message_id += 1
        self.sock.sendall(struct.pack('!i', self.send_message_id))
        self.sock.sendall(struct.pack('!H', len(data)))
        self.sock.sendall(data)

    def receive_event(self):
        message_id = struct.unpack('!i', self.sock.recv(4))
        data_len = struct.unpack('!H', self.sock.recv(2))
        data = self.sock.recv(data_len)
        if last_recv_message_id and last_recv_message_id != (message_id + 1):
            raise RuntimeError('out of sync')
        else:
            last_recv_message_id = message_id
        return read_event(data)
