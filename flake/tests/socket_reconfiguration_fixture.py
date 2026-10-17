"""Synthetic socket activation, accepted-worker and continuity probes."""

import os
import selectors
import socket
import sys
import time
from pathlib import Path


def connect(address):
    if address.startswith("/"):
        connection = socket.socket(socket.AF_UNIX)
        connection.settimeout(5)
        connection.connect(address)
        return connection
    return socket.create_connection(("127.0.0.1", int(address)), timeout=5)


mode = sys.argv[1]
if mode == "accepted":
    for line in sys.stdin.buffer:
        sys.stdout.buffer.write(str(os.getpid()).encode() + b":" + line)
        sys.stdout.buffer.flush()
elif mode in {"probe", "hold"}:
    with connect(sys.argv[2]) as connection:
        incoming = connection.makefile("rb")
        counter = 0
        while True:
            connection.sendall(b"probe\n")
            reply = incoming.readline().decode().strip()
            assert reply.endswith(":probe"), reply
            if mode == "probe":
                print(reply)
                break
            destination = Path(sys.argv[3])
            temporary = destination.with_suffix(".tmp")
            temporary.write_text(f"{counter} {reply.split(':')[0]}\n")
            temporary.replace(destination)
            counter += 1
            time.sleep(0.1)
elif mode == "activated":
    assert os.environ["LISTEN_PID"] == str(os.getpid())
    selector = selectors.DefaultSelector()
    for descriptor in range(3, 3 + int(os.environ["LISTEN_FDS"])):
        listener = socket.socket(fileno=descriptor)
        listener.setblocking(False)
        selector.register(listener, selectors.EVENT_READ, True)
    while True:
        for event, _ in selector.select():
            if event.data:
                connection, _ = event.fileobj.accept()
                selector.register(connection, selectors.EVENT_READ, False)
            else:
                data = event.fileobj.recv(4096)
                if data:
                    event.fileobj.sendall(str(os.getpid()).encode() + b":" + data)
                else:
                    selector.unregister(event.fileobj)
                    event.fileobj.close()
else:
    raise ValueError(mode)
