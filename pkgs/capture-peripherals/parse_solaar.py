import json
import re
import sys

text = sys.stdin.read()

name_re = re.compile(r"^\s*Codename\s*:\s*(.+?)\s*$", re.MULTILINE)
battery_re = re.compile(r"Battery:\s*(\d+)%\s*(\d+)mV\s*,\s*BatteryStatus\.(\w+)")
unitid_re = re.compile(r"^\s*Unit ID:\s*(\S+)", re.MULTILINE)

matches = list(name_re.finditer(text))
devices = []
for i, m in enumerate(matches):
    start = m.end()
    end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
    block = text[start:end]
    bat = battery_re.search(block)
    uid = unitid_re.search(block)
    if not bat:
        continue
    devices.append(
        {
            "name": m.group(1),
            "unit_id": uid.group(1) if uid else None,
            "battery_percent": int(bat.group(1)),
            "battery_mv": int(bat.group(2)),
            "battery_status": bat.group(3),
        }
    )

print(json.dumps({"devices": devices}))
