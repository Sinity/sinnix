"""AI CLI discovery and lifecycle labels with an unavailable hub."""
import json
import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory(prefix="ai-cli-test-") as temporary:
    root = Path(temporary)
    fake = root / "systemctl"
    fake.write_text(f"#!{sys.executable}\n" + """import json,os,sys
from pathlib import Path
args=sys.argv[1:]
with Path(os.environ['SYSTEMCTL_LOG']).open('a') as handle: handle.write(json.dumps(args)+'\\n')
if 'cat' in args:
    sys.exit(0 if args[-1] in ('direct-ai.service','proxy-ai.service','proxy-ai-proxy.service') else 1)
if 'is-active' in args:
    if '--quiet' not in args: print('inactive')
    sys.exit(3)
if 'show' in args:
    if 'ExecStart' in args: sys.exit(1)
    sys.exit(0)
sys.exit(1)
""")
    compile(fake.read_text(), str(fake), "exec")
    fake.chmod(0o700)
    inventory = root / "inventory.json"
    calls = root / "systemctl.jsonl"
    env = {**os.environ, 'PATH': str(root) + os.pathsep + os.environ['PATH'], 'SINNIX_RUNTIME_INVENTORY_FILE': str(inventory), 'SYSTEMCTL_LOG': str(calls)}
    def run(*arguments):
        return subprocess.run(['bash', sys.argv[1], *arguments], env=env, capture_output=True, text=True, timeout=5)
    surfaces = {
        'direct-ai': {'ai': {'backendKind': 'native'}, 'unit': 'direct-ai.service', 'activation': {'mode': 'direct', 'publicEndpoint': '127.0.0.1:1234'}},
        'proxy-ai': {'ai': {'backendKind': 'native'}, 'unit': 'proxy-ai.service', 'activation': {'mode': 'socket-proxy', 'publicEndpoint': '127.0.0.1:1235'}},
        'ordinary': {'ai': None, 'unit': 'ordinary.service', 'activation': {'mode': 'direct'}},
    }
    inventory.write_text(json.dumps({'surfaces': surfaces}))
    launcher = root / 'systemd-run'
    launch_log = root / 'launch.json'
    launcher.write_text(f'#!{sys.executable}\n' + "import json,sys\nfrom pathlib import Path\n" + f"Path({str(launch_log)!r}).write_text(json.dumps(sys.argv[1:]))\n")
    launcher.chmod(0o700)
    pinned = run('pin', 'proxy-ai', '2s')
    assert pinned.returncode == 0, pinned.stderr
    launch = json.loads(launch_log.read_text())
    assert '--user' in launch and '--property=RuntimeMaxSec=2' in launch, launch
    holder = launch[launch.index('--') + 1:]
    assert holder[:2] == ['python3', '-c'], holder
    assert holder[-1] == '/run/sinnix-ai/proxy-ai-proxy.sock', holder
    # Exercise the exact holder code captured from the CLI, substituting
    # only the socket address. Closing the backend must release the pin.
    with socket.socket(socket.AF_UNIX) as listener:
        address = str(root / 'pin.sock')
        listener.bind(address)
        listener.listen(1)
        listener.settimeout(2)
        process = subprocess.Popen([*holder[:-1], address], env=env)
        try:
            connection, _ = listener.accept()
            assert process.poll() is None
            connection.close()
            assert process.wait(timeout=2) == 0
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=2)
    result = run('list')
    assert result.returncode == 0, result.stderr
    rows = {line.split()[0]: line.split() for line in result.stdout.splitlines()[1:]}
    assert set(rows) == {'direct-ai', 'proxy-ai'}, result.stdout
    assert rows['direct-ai'][3] == 'manual', result.stdout
    assert rows['proxy-ai'][3] == 'on-demand', result.stdout
    detail = run('status', 'direct-ai')
    assert detail.returncode == 0 and 'manual' in detail.stdout, detail
    assert 'backend is not running' in detail.stdout
    assert not any('sinnix-ops-reducer.service' in json.loads(line) for line in calls.read_text().splitlines())
    before = calls.read_bytes()
    for name in ('--help', '--version', '-e'):
        result = run('start', name)
        assert result.returncode != 0 and 'unknown service:' in result.stderr, result
        assert not result.stdout, result.stdout
    assert calls.read_bytes() == before, 'invalid names reached systemctl'
    for content in ('{', '{"surfaces": null}', '{"surfaces": []}'):
        inventory.write_text(content)
        result = run('list')
        assert result.returncode != 0 and result.stderr, result
    inventory.unlink()
    result = run('list')
    assert result.returncode != 0 and 'unreadable' in result.stderr, result
    inventory.write_text('{"surfaces": {}}')
    result = run('list')
    assert result.returncode == 0 and len(result.stdout.splitlines()) == 1, result
    print('AI CLI: direct and proxy discovery independent of hub; accurate lifecycle; missing/malformed versus valid empty inventory')
