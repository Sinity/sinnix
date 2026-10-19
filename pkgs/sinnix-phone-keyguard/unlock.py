#!/usr/bin/env python3
"""Install the immutable root helper and request a bounded native unlock lease."""

import hashlib
import pathlib
import shlex
import subprocess
import sys
import time


def main():
    if len(sys.argv) != 4:
        raise SystemExit("usage: sinnix-phone-keyguard SERIAL DEX SECONDS")
    serial, dex, duration = sys.argv[1:]
    seconds = int(duration)
    if not 1 <= seconds <= 600:
        raise SystemExit("duration must be 1..600 seconds")
    adb = ["adb", "-s", serial]

    def shell(args, **kwargs):
        return subprocess.run(
            adb + ["shell", shlex.join(args)], check=True, text=True, **kwargs
        )

    state = shell(
        ["am", "get-started-user-state", "0"], capture_output=True
    ).stdout.strip()
    user = shell(["am", "get-current-user"], capture_output=True).stdout.strip()
    if state != "RUNNING_UNLOCKED" or user != "0":
        raise SystemExit(
            "user 0 must already be decrypted and current; first boot unlock is not automated"
        )
    root = shell(["su", "-c", "id -u"], capture_output=True).stdout.strip()
    if root != "0":
        raise SystemExit("authorized root unavailable")
    digest = hashlib.sha256(pathlib.Path(dex).read_bytes()).hexdigest()
    home = "/data/adb/sinnix-phone-keyguard"
    target = f"{home}/{digest}.dex"
    scratch = f"/data/local/tmp/sinnix-keyguard-{digest}.dex"
    subprocess.run(adb + ["push", dex, scratch], check=True, capture_output=True)
    command = f"CLASSPATH={target}:/system/framework/org.lineageos.platform.jar app_process /system/bin PhoneKeyguard"
    hook = (
        "#!/system/bin/sh\n# Sinnix-owned bounded phone keyguard recovery.\n"
        'i=0\nwhile [ "$(getprop sys.boot_completed)" != 1 ]; do\n'
        ' [ "$i" -lt 180 ] || exit 1\n sleep 2\n i=$((i+1))\ndone\n'
        f"{command} recover\n"
    )
    install = (
        f"set -e; umask 077; mkdir -p {home}; chmod 700 {home}; "
        f"test \"$(sha256sum {scratch} | cut -d ' ' -f 1)\" = {digest}; "
        f"cp {scratch} {target}.new; chmod 400 {target}.new; mv {target}.new {target}; "
        "test -d /data/adb/service.d; "
        "if [ -e /data/adb/service.d/sinnix-keyguard-recovery.sh ]; then "
        "grep -q '^# Sinnix-owned bounded phone keyguard recovery.$' /data/adb/service.d/sinnix-keyguard-recovery.sh; fi; "
        f"printf %s {shlex.quote(hook)} > /data/adb/service.d/.sinnix-keyguard-recovery.new; "
        "chmod 700 /data/adb/service.d/.sinnix-keyguard-recovery.new; "
        "mv /data/adb/service.d/.sinnix-keyguard-recovery.new /data/adb/service.d/sinnix-keyguard-recovery.sh; "
        f"rm {scratch}"
    )
    shell(["su", "-c", install])
    # Foreground lease reports activation; the independent phone watchdog is
    # already armed when the lock policy changes. Disconnecting ADB is safe.
    process = subprocess.Popen(
        adb + ["shell", shlex.join(["su", "-c", f"umask 077; {command} {seconds}"])],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        for line in process.stdout:
            print(line.strip(), flush=True)
            if line.strip() == "UNLOCK_LEASE_ACTIVE":
                shell(["input", "keyevent", "KEYCODE_WAKEUP"])
                shell(["wm", "dismiss-keyguard"])
                deadline = time.monotonic() + 3
                while True:
                    status = shell(
                        ["dumpsys", "window", "policy"], capture_output=True
                    ).stdout
                    if "mIsShowing=false" in status:
                        break
                    if time.monotonic() >= deadline:
                        raise RuntimeError("native keyguard did not dismiss")
                    time.sleep(0.1)
                print("KEYGUARD_DISMISSED", flush=True)
        if process.wait() != 0:
            raise RuntimeError("unlock lease failed")
    finally:
        if process.poll() is None:
            process.terminate()


if __name__ == "__main__":
    main()
