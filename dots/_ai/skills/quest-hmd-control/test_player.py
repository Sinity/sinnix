import argparse
import http.client
import pathlib
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch

import player


class PlayerTest(unittest.TestCase):
    def test_fragmented_protocol(self):
        left, right = socket.socketpair()
        with left, right:
            data = b'{"currentTime":12}'
            wire = player.struct.pack('<I', len(data)) + data
            def send():
                for byte in wire:
                    left.sendall(bytes([byte]))
            thread = threading.Thread(target=send)
            thread.start()
            self.assertEqual(player.receive(right), {'currentTime': 12})
            thread.join()

    def test_file_ranges_and_descriptor(self):
        with tempfile.TemporaryDirectory() as directory:
            source = pathlib.Path(directory) / 'movie.mp4'
            source.write_bytes(b'0123456789')
            args = argparse.Namespace(file=str(source), stereo='sbs', projection='flat', codec='h264', height=720, cold=False)
            calls = []
            def adb(*args):
                calls.append(args)
                if args[0] != 'shell':
                    return ''
                link = player.shlex.split(args[1])[-1].removeprefix('deovr://')
                from urllib.parse import urlsplit
                url = urlsplit(link)
                connection = http.client.HTTPConnection(url.hostname, url.port)
                connection.request('GET', url.path)
                response = connection.getresponse()
                descriptor = player.json.loads(response.read())
                self.assertEqual(descriptor['stereoMode'], 'sbs')
                route = urlsplit(descriptor['encodings'][0]['videoSources'][0]['url']).path
                for requested, expected, interval in [('bytes=2-5', b'2345', 'bytes 2-5/10'), ('bytes=-3', b'789', 'bytes 7-9/10'), ('bytes=8-', b'89', 'bytes 8-9/10')]:
                    connection.request('GET', route, headers={'Range': requested})
                    response = connection.getresponse()
                    self.assertEqual(response.status, 206)
                    self.assertEqual(response.getheader('Content-Range'), interval)
                    self.assertEqual(response.read(), expected)
                connection.request('GET', route, headers={'Range': 'bytes=20-'})
                response = connection.getresponse()
                self.assertEqual(response.status, 416)
                response.read()
                connection.request('GET', '/etc/passwd')
                response = connection.getresponse()
                self.assertEqual(response.status, 404)
                response.read()
                connection.close()
                return ''
            with patch.object(player, 'adb', side_effect=adb), patch.object(player.time, 'sleep', side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    player.serve(args)
            self.assertEqual(calls[-1][:2], ('reverse', '--remove'))


if __name__ == '__main__':
    unittest.main()
