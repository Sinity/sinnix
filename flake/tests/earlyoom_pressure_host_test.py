"""Real owned-child cancellation/exception cleanup without starting a VM."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class HostLifecycle(unittest.TestCase):
    def test_owned_children_cleanup(self):
        for failure in (
            "normal",
            "exception",
            "SIGTERM",
            "identity-race",
            "killpg-race",
        ):
            with (
                self.subTest(failure=failure),
                tempfile.TemporaryDirectory(
                    dir=os.environ.get("TMPDIR", "/realm/tmp/work")
                ) as temp,
            ):
                root = Path(temp)
                driver = root / "driver" / "bin"
                driver.mkdir(parents=True)
                qemu = root / "qemu-system-fixture"
                qemu.symlink_to(sys.executable)
                vde = root / ".vde_switch-wrapped"
                vde.symlink_to(sys.executable)
                executable = driver / "nixos-test-driver"
                executable.write_text(
                    f'#!{sys.executable}\nimport subprocess,time\np=subprocess.Popen([{str(qemu)!r},"-c","import time;time.sleep(1)"])\nv=subprocess.Popen([{str(vde)!r},"-c","import time;time.sleep(1)"])\np.wait()\nv.wait()\n'
                )
                executable.chmod(0o700)
                bootstrap = root / "check.py"
                bootstrap.write_text("""import os,runpy,signal,subprocess,sys,time
from pathlib import Path
from unittest.mock import patch
source,driver,output,failure=sys.argv[1:]
original_read=Path.read_text
original_run=subprocess.run
original_sleep=time.sleep
original_killpg=os.killpg
calls=0
stat_reads=0
kill_calls=0
rows=[]
for mount in ('/realm','/nix'):
    source_device=subprocess.check_output(['findmnt','--noheadings','--output','SOURCE','--target',mount],text=True).strip().split('[',1)[0]
    dev=os.stat(source_device).st_rdev
    device=f'{os.major(dev)}:{os.minor(dev)}'
    sysdev=Path('/sys/dev/block',device).resolve()
    if (sysdev/'partition').exists(): device=(sysdev.parent/'dev').read_text().strip()
    rows.append(f'{device} rbps=8000000 wbps=8000000 riops=max wiops=max')
def read(path,*args,**kwargs):
    if str(path).startswith('/sys/fs/cgroup/'):
        if path.name=='memory.max': return '4294967296'
        if path.name=='memory.swap.max': return '0'
        if path.name=='io.max': return '\\n'.join(set(rows))
    if failure=='identity-race' and str(path).startswith('/proc/') and path.name=='stat':
        global stat_reads
        stat_reads+=1
        text=original_read(path,*args,**kwargs)
        head,tail=text.rsplit(')',1)
        parts=tail.split()
        parts[19]=str(int(parts[19])+stat_reads%2)
        return head+') '+' '.join(parts)
    return original_read(path,*args,**kwargs)
def build(args,*a,**kw):
    if args[0]=='nix':
        assert args[-1]=='.#packages.x86_64-linux.earlyoom-real-pressure-driver',args
        return subprocess.CompletedProcess(args,0,driver+'\\n')
    return original_run(args,*a,**kw)
def sleep(seconds):
    global calls
    original_sleep(seconds)
    calls+=1
    if calls==3 and failure=='SIGTERM': os.kill(os.getpid(),signal.SIGTERM)
    if calls==3 and failure in ('exception','killpg-race'): raise RuntimeError('fixture-exception')
def killpg(pid,sig):
    global kill_calls
    kill_calls+=1
    if failure=='killpg-race' and kill_calls==1: raise ProcessLookupError('already gone')
    return original_killpg(pid,sig)
sys.argv=[source,output]
with patch.object(Path,'read_text',read),patch.object(subprocess,'run',build),patch.object(time,'sleep',sleep),patch.object(os,'killpg',killpg):
    try: runpy.run_path(source,run_name='__main__')
    except (SystemExit,RuntimeError,AssertionError):
        if failure=='normal': raise
""")
                output = root / ("canonical-output-" + "x" * 140) / "out"
                result = subprocess.run(
                    [
                        sys.executable,
                        str(bootstrap),
                        str(Path(__file__).with_name("earlyoom_pressure_host.py")),
                        str(driver.parent),
                        str(output),
                        failure,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                receipt = json.loads((output / "host-receipt.json").read_text())
                if failure == "identity-race":
                    self.assertFalse(receipt["qemu"], receipt)
                else:
                    self.assertTrue(receipt["qemu"], receipt)
                    self.assertEqual(
                        {p["kind"] for p in receipt["qemu"].values()},
                        {"qemu", "vde"},
                        receipt,
                    )
                self.assertTrue(
                    all(p["terminal"] for p in receipt["qemu"].values()), receipt
                )
                self.assertIsNotNone(receipt["driver_returncode"], receipt)
                self.assertLess(
                    len(os.fsencode(Path(receipt["runtime_root"]) / "vde1.ctl/ctl"))
                    + 1,
                    109,
                )
                self.assertTrue(receipt["runtime_cleaned"], receipt)
                self.assertFalse(Path(receipt["runtime_root"]).exists(), receipt)


if __name__ == "__main__":
    unittest.main()
