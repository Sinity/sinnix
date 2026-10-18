"""Exercise the exact native NATS binary using isolated, synthetic broker state."""
import argparse
import base64
import http.client
import json
from pathlib import Path
import signal
import socket
import subprocess
import tempfile
import time
import urllib.parse


class Broker:
    def __init__(self, executable, root):
        self.executable, self.root = executable, root
        self.process = None
        self.log = None
        self.config = root / 'nats.conf'
        self.config.write_text(
            'server_name: "neutral-monitor-fixture"\nhost: "127.0.0.1"\nport: -1\n'
            'http: "127.0.0.1:-1"\nhttp_base_path: "/monitor"\n'
            f'ports_file_dir: {json.dumps(str(root))}\n'
            f'jetstream {{ store_dir: {json.dumps(str(root / "jetstream"))}, '
            'max_memory_store: 8Mb, max_file_store: 32Mb }\n'
        )

    def start(self):
        self.log = (self.root / 'server.log').open('a')
        self.process = subprocess.Popen([self.executable, '-c', str(self.config)], stdout=self.log, stderr=self.log)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise AssertionError((self.root / 'server.log').read_text())
            files = list(self.root.glob(f'*_{self.process.pid}.ports'))
            if files:
                try:
                    info = json.loads(files[0].read_text())
                except json.JSONDecodeError:
                    pass
                else:
                    self.monitor = urllib.parse.urlsplit(info['monitoring'][0])
                    self.client = urllib.parse.urlsplit(info['nats'][0])
                    return
            time.sleep(.02)
        raise AssertionError('owned fixture did not publish its ports within 10 seconds')

    def stop(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.send_signal(signal.SIGTERM)
                try:
                    self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
                    raise AssertionError('owned fixture did not stop gracefully')
            assert self.process.returncode == 0, (self.root / 'server.log').read_text()
            self.process = None
        if self.log:
            self.log.close()
            self.log = None

    def request(self, headers=(), method='GET', path='/connz?limit=1', partial=False):
        c = http.client.HTTPConnection(self.monitor.hostname, self.monitor.port, timeout=2)
        started = time.monotonic()
        try:
            c.putrequest(method, '/monitor' + path, skip_host=True, skip_accept_encoding=True)
            if not any(name.lower() == 'host' for name, _ in headers):
                c.putheader('Host', self.monitor.netloc)
            for name, value in headers:
                c.putheader(name, value)
            if partial:
                c.putheader('Content-Length', '4096')
            c.endheaders()
            if partial:
                c.send(b'x')
            r = c.getresponse()
            body = r.read(262144)
            return r.status, dict(r.getheaders()), body, time.monotonic() - started
        finally:
            c.close()


class Wire:
    def __init__(self, address):
        self.socket = socket.create_connection((address.hostname, address.port), timeout=3)
        self.socket.settimeout(3)
        self.reader = self.socket.makefile('rb')
        assert self.reader.readline().startswith(b'INFO ')
        self.socket.sendall(b'CONNECT {"verbose":false,"pedantic":true}\r\nPING\r\n')
        self.wait('PONG')
        self.sid = 0

    def close(self):
        self.reader.close()
        self.socket.close()

    def wait(self, expected):
        while True:
            line = self.reader.readline()
            assert line, 'native broker connection closed'
            if line.startswith(b'-ERR'):
                raise AssertionError(line.decode())
            if line == b'PING\r\n':
                self.socket.sendall(b'PONG\r\n')
            elif expected == 'PONG' and line == b'PONG\r\n':
                return None
            elif line.startswith(b'MSG '):
                size = int(line.split()[-1])
                assert size <= 65536
                payload = self.reader.read(size)
                assert self.reader.read(2) == b'\r\n'
                if expected == 'MSG':
                    return payload

    def request(self, subject, payload):
        self.sid += 1
        inbox = f'_INBOX.neutral.{self.sid}'
        command = f'SUB {inbox} {self.sid}\r\nPUB {subject} {inbox} {len(payload)}\r\n'.encode()
        self.socket.sendall(command + payload + b'\r\n')
        result = json.loads(self.wait('MSG'))
        assert 'error' not in result, result
        return result

    def pubsub(self):
        self.sid += 1
        body = b'neutral pubsub proof'
        self.socket.sendall(f'SUB neutral.live {self.sid}\r\nPUB neutral.live {len(body)}\r\n'.encode() + body + b'\r\n')
        assert self.wait('MSG') == body


def check(executable, baseline=False):
    with tempfile.TemporaryDirectory(prefix='nats-monitor-test-') as tmp:
        broker = Broker(executable, Path(tmp))
        try:
            broker.start()
            local = broker.monitor.netloc
            origin = f'http://localhost:{broker.monitor.port}'
            status, headers, body, _ = broker.request()
            assert status == 200 and 'connections' in json.loads(body)
            rejected = 0
            if baseline:
                for extra in [[('Host', f'untrusted.invalid:{broker.monitor.port}')], [('Origin', 'https://untrusted.invalid')]]:
                    status, headers, body, _ = broker.request(extra)
                    assert status == 200 and headers.get('Access-Control-Allow-Origin') == '*'
                    assert 'connections' in json.loads(body)
            else:
                assert 'Access-Control-Allow-Origin' not in headers
                positives = [
                    [('Host', f'localhost:{broker.monitor.port}')],
                    [('Host', f'[::1]:{broker.monitor.port}')],
                    [('Origin', origin), ('Sec-Fetch-Site', 'cross-site'), ('Sec-Fetch-Mode', 'cors')],
                    [('Origin', f'http://{local}'), ('Sec-Fetch-Site', 'same-origin')],
                    [('Sec-Fetch-Site', 'none'), ('Sec-Fetch-Mode', 'navigate'), ('Sec-Fetch-Dest', 'document'), ('Sec-Fetch-User', '?1')],
                    [('Sec-Fetch-Site', 'cross-site'), ('Sec-Fetch-Mode', 'navigate'), ('Sec-Fetch-Dest', 'document'), ('Sec-Fetch-User', '?1')],
                ]
                for values in positives:
                    status, response, body, _ = broker.request(values)
                    assert status == 200, (values, status, body)
                    assert response.get('Access-Control-Allow-Origin') == dict(values).get('Origin')
                    assert response.get('Cache-Control') == 'no-store'
                assert broker.request(method='HEAD')[0] == 200
                before = sum(json.loads(broker.request(path='/varz')[2])['http_req_stats'].values())
                negatives = [
                    [('Host', f'untrusted.invalid:{broker.monitor.port}')],
                    [('Host', f'localhost:{broker.monitor.port + 1}')],
                    [('Host', local), ('Host', local)],
                    [('Origin', 'https://untrusted.invalid')],
                    [('Origin', f'http://untrusted.invalid:{broker.monitor.port}')],
                    [('Origin', 'null')], [('Origin', '')],
                    [('Origin', origin + '/')], [('Origin', origin + '/private')],
                    [('Origin', origin + '?')], [('Origin', origin + '#')],
                    [('Origin', origin.replace('://', '://user@'))],
                    [('Origin', origin), ('Origin', origin)],
                    [('Sec-Fetch-Site', 'cross-site')],
                    [('Sec-Fetch-Site', 'same-site'), ('Sec-Fetch-Mode', 'no-cors'), ('Sec-Fetch-Dest', 'script')],
                    [('Sec-Fetch-Site', 'cross-site'), ('Sec-Fetch-Mode', 'navigate'), ('Sec-Fetch-Dest', 'iframe'), ('Sec-Fetch-User', '?1')],
                    [('Sec-Fetch-Site', 'cross-site'), ('Sec-Fetch-Mode', 'navigate'), ('Sec-Fetch-Dest', 'document')],
                    [('Sec-Fetch-Site', 'unknown')], [('Sec-Fetch-Mode', 'cors')],
                    [('Sec-Fetch-Site', 'same-origin'), ('Sec-Fetch-Site', 'same-origin')],
                    [('Sec-Fetch-Site', 'same-origin'), ('Sec-Fetch-Mode', 'unknown')],
                    [('Sec-Fetch-Site', 'same-origin'), ('Sec-Fetch-User', '?0')],
                ]
                for values in negatives:
                    status, response, body, _ = broker.request(values)
                    assert status in (400, 403), (values, status, body)
                    assert response.get('Access-Control-Allow-Origin') != '*'
                    assert 'server_id' not in body.decode()
                    rejected += 1
                for name in ['Origin', 'Sec-Fetch-Site', 'Sec-Fetch-Mode', 'Sec-Fetch-Dest', 'Sec-Fetch-User']:
                    values = [('Sec-Fetch-Site', 'same-origin')] if name != 'Sec-Fetch-Site' else []
                    value = origin if name == 'Origin' else 'same-origin' if name == 'Sec-Fetch-Site' else 'cors' if name == 'Sec-Fetch-Mode' else 'empty' if name == 'Sec-Fetch-Dest' else '?1'
                    values += [(name, value), (name, value)]
                    assert broker.request(values)[0] == 403
                    rejected += 1
                for method in ['POST', 'OPTIONS']:
                    status, _, body, elapsed = broker.request([('Origin', 'https://untrusted.invalid')], method=method, partial=True)
                    assert status == 403 and elapsed < 1, (status, elapsed, body)
                    rejected += 1
                after = sum(json.loads(broker.request(path='/varz')[2])['http_req_stats'].values())
                assert after == before + 1, (before, after)
            wire = Wire(broker.client)
            try:
                wire.pubsub()
                wire.request('$JS.API.STREAM.CREATE.NEUTRAL_PROOF', json.dumps({'name': 'NEUTRAL_PROOF', 'subjects': ['neutral.persist'], 'storage': 'file', 'max_msgs': 10}).encode())
                ack = wire.request('neutral.persist', b'neutral retained message')
                assert ack['stream'] == 'NEUTRAL_PROOF' and ack['seq'] == 1
            finally:
                wire.close()
            broker.stop()
            broker.start()
            wire = Wire(broker.client)
            try:
                wire.pubsub()
                response = wire.request('$JS.API.STREAM.MSG.GET.NEUTRAL_PROOF', b'{"seq":1}')
                assert base64.b64decode(response['message']['data']) == b'neutral retained message'
            finally:
                wire.close()
            assert broker.request(path='/healthz')[0] == 200
            return {'baseline': baseline, 'refusals': rejected, 'native_monitor': True, 'native_pubsub': True, 'jetstream_restart_preserved': True}
        finally:
            broker.stop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('executable')
    parser.add_argument('--baseline', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.executable, args.baseline)))
