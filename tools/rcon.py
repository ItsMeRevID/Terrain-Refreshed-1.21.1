#!/usr/bin/env python3
"""Minimal RCON client used to drive the dev server console.

The Gradle daemon does not forward its stdin to the forked server process, so the
console is reached over RCON instead.

Usage: rcon.py <host> <port> <password> <command> [command ...]
"""

import socket
import struct
import sys

TYPE_AUTH = 3
TYPE_COMMAND = 2
TYPE_RESPONSE = 0


def pack(request_id, packet_type, body):
    payload = struct.pack("<ii", request_id, packet_type) + body.encode("utf-8") + b"\x00\x00"
    return struct.pack("<i", len(payload)) + payload


def read_packet(sock):
    header = sock.recv(4)
    if len(header) < 4:
        raise ConnectionError("connection closed while reading header")
    length = struct.unpack("<i", header)[0]
    data = b""
    while len(data) < length:
        chunk = sock.recv(length - len(data))
        if not chunk:
            raise ConnectionError("connection closed while reading body")
        data += chunk
    request_id, packet_type = struct.unpack("<ii", data[:8])
    return request_id, packet_type, data[8:-2].decode("utf-8", "replace")


class Rcon:
    def __init__(self, host, port, password, timeout=600.0):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(timeout)
        self.request_id = 0
        self.authenticate(password)

    def next_id(self):
        self.request_id += 1
        return self.request_id

    def authenticate(self, password):
        self.sock.sendall(pack(self.next_id(), TYPE_AUTH, password))
        request_id, packet_type, body = read_packet(self.sock)
        if request_id == -1:
            raise PermissionError("rcon authentication failed")

    def command(self, text):
        self.sock.sendall(pack(self.next_id(), TYPE_COMMAND, text))
        request_id, packet_type, body = read_packet(self.sock)
        return body

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def main():
    if len(sys.argv) < 5:
        print(__doc__.strip())
        return 2
    host, port, password = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    rcon = Rcon(host, port, password)
    try:
        for command in sys.argv[4:]:
            print("> " + command)
            print(rcon.command(command).strip())
    finally:
        rcon.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
