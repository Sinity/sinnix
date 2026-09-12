#!/usr/bin/env python3
"""Foreground DeoVR launcher and bounded TCP remote-control client."""
import argparse
import json
import math
import mimetypes
import pathlib
import re
import secrets
import shlex
import socket
import struct
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def adb(*args):
    return subprocess.check_output(['sinnix', 'quest', 'adb', *args], text=True).strip()


def packet(sock, data):
    body = json.dumps(data).encode() if data else b''
    sock.sendall(struct.pack('<I', len(body)) + body)


def receive(sock):
    def exact(size):
        data = b''
        while len(data) < size:
            chunk = sock.recv(size - len(data))
            if not chunk:
                raise RuntimeError('DeoVR closed the connection')
            data += chunk
        return data
    size = struct.unpack('<I', exact(4))[0]
    if size > 1048576:
        raise RuntimeError('Invalid DeoVR packet length')
    return json.loads(exact(size)) if size else {}


def remote(args):
    port = int(adb('forward', 'tcp:0', 'tcp:23554'))
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=2) as sock:
            packet(sock, {})
            state = {}
            deadline = time.monotonic() + 5
            while not state and time.monotonic() < deadline:
                state = receive(sock)
                packet(sock, {})
            if not state:
                raise RuntimeError('DeoVR connected but has no active video')
            if args.action == 'status':
                print(json.dumps(state, indent=2))
                return
            if args.action == 'seek':
                value = float(args.value)
                if not math.isfinite(value):
                    raise ValueError('seek must be finite')
                if args.value.startswith(('+', '-')):
                    value += state['currentTime']
                update = {'currentTime': max(0, min(value, state['duration']))}
            elif args.action == 'speed':
                value = float(args.value)
                if not math.isfinite(value) or not 0.1 <= value <= 4:
                    raise ValueError('speed must be between 0.1 and 4')
                update = {'playbackSpeed': value}
            else:
                update = {'playerState': 1 if args.action == 'pause' else 0}
            packet(sock, update)
            for _ in range(4):
                state = receive(sock)
                packet(sock, {})
                if state and all(abs(state.get(k, -999) - v) < (2 if k == 'currentTime' else 0.01) for k, v in update.items()):
                    print(json.dumps(update))
                    return
            raise RuntimeError('Command sent but requested state was not observed; this player may not support it')
    finally:
        adb('forward', '--remove', f'tcp:{port}')


def serve(args):
    path = pathlib.Path(args.file).resolve(strict=True)
    if not path.is_file():
        raise ValueError('Expected a video file')
    token = secrets.token_urlsafe(20)
    video_route = f'/{token}/video{path.suffix}'
    descriptor_route = f'/{token}/video.json'
    accessed = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *unused):
            pass

        def do_HEAD(self):
            self.respond(False)

        def do_GET(self):
            self.respond(True)

        def respond(self, body):
            if self.path == descriptor_route:
                print('DeoVR requested the video descriptor.', flush=True)
                data = json.dumps({'title': path.stem, 'is3d': args.stereo != 'off', 'stereoMode': args.stereo, 'screenType': args.projection, 'encodings': [{'name': args.codec, 'videoSources': [{'resolution': args.height, 'url': f'http://127.0.0.1:{server.server_port}{video_route}'}]}]}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                if body:
                    self.wfile.write(data)
                return
            if self.path != video_route:
                self.send_error(404)
                return
            size = path.stat().st_size
            start, end = 0, size - 1
            requested = self.headers.get('Range')
            if requested:
                match = re.fullmatch(r'bytes=(\d*)-(\d*)', requested)
                if not match or not any(match.groups()):
                    self.send_error(416)
                    return
                first, last = match.groups()
                if first:
                    start = int(first)
                    end = min(int(last), end) if last else end
                else:
                    start = max(0, size - int(last))
                if start > end or start >= size:
                    self.send_response(416)
                    self.send_header('Content-Range', f'bytes */{size}')
                    self.end_headers()
                    return
            self.send_response(206 if requested else 200)
            self.send_header('Content-Type', mimetypes.guess_type(path)[0] or 'application/octet-stream')
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Content-Length', str(end - start + 1))
            if requested:
                self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
            self.end_headers()
            if body:
                accessed.set()
                with path.open('rb') as source:
                    source.seek(start)
                    remaining = end - start + 1
                    try:
                        while remaining:
                            chunk = source.read(min(remaining, 262144))
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            remaining -= len(chunk)
                    except (BrokenPipeError, ConnectionResetError):
                        pass

    with ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
        port = server.server_port
        adb('reverse', f'tcp:{port}', f'tcp:{port}')
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            link = f'deovr://http://127.0.0.1:{port}{descriptor_route}'
            adb('shell', 'am start ' + ('-S ' if args.cold else '') + '-a android.intent.action.VIEW -n com.deovr.gearvr/com.unity3d.player.UnityPlayerActivity -d ' + shlex.quote(link))
            if accessed.wait(20):
                print('DeoVR requested video bytes. Keep this process running; Ctrl-C ends serving.', flush=True)
            else:
                print('No video request yet. Check headset unlock/onboarding; server remains available.', flush=True)
            while True:
                time.sleep(1)
        finally:
            server.shutdown()
            adb('reverse', '--remove', f'tcp:{port}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    play = sub.add_parser('open', help='Serve one local file over ADB and launch DeoVR; stays foreground')
    play.add_argument('file')
    play.add_argument('--stereo', choices=['sbs', 'tb', 'off'], default='sbs')
    play.add_argument('--projection', choices=['flat', 'dome', 'sphere'], default='flat')
    play.add_argument('--codec', choices=['h264', 'h265', 'av1'], default='h264')
    play.add_argument('--height', type=int, default=1080)
    play.add_argument('--cold', action='store_true', help='Restart DeoVR before sending the link')
    for name in ['status', 'pause', 'resume', 'seek', 'speed']:
        command = sub.add_parser(name)
        if name in ['seek', 'speed']:
            command.add_argument('value')
    args = parser.parse_args()
    try:
        serve(args) if args.action == 'open' else remote(args)
    except KeyboardInterrupt:
        pass
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'{error}\nRemote commands require DeoVR running with Enable remote control switched on and an active video.\n')


if __name__ == '__main__':
    main()
