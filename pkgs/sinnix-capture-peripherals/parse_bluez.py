"""Flatten bluez's ObjectManager dump into device battery + AVRCP records.

Reads `busctl call org.bluez / org.freedesktop.DBus.ObjectManager
GetManagedObjects --json=short` on stdin (the whole object tree in one
call, rather than walking it live) and emits two JSON arrays: one entry
per org.bluez.Battery1 interface (percentage, source, owning device alias)
and one per org.bluez.MediaTransport1 interface (state, codec, volume).
"""

import json
import sys


def unwrap(props, key, default=None):
    v = props.get(key)
    return v["data"] if v is not None else default


def main():
    dump = json.load(sys.stdin)
    objects = dump["data"][0]

    devices = {}
    for path, ifaces in objects.items():
        dev = ifaces.get("org.bluez.Device1")
        if dev:
            devices[path] = {
                "address": unwrap(dev, "Address"),
                "alias": unwrap(dev, "Alias"),
                "connected": unwrap(dev, "Connected"),
            }

    battery = []
    transport = []
    for _path, ifaces in objects.items():
        bat = ifaces.get("org.bluez.Battery1")
        if bat:
            dev_path = unwrap(bat, "Device")
            dev = devices.get(dev_path, {})
            battery.append(
                {
                    "device_address": dev.get("address"),
                    "device_alias": dev.get("alias"),
                    "percentage": unwrap(bat, "Percentage"),
                    "source": unwrap(bat, "Source"),
                }
            )
        mt = ifaces.get("org.bluez.MediaTransport1")
        if mt:
            dev_path = unwrap(mt, "Device")
            dev = devices.get(dev_path, {})
            transport.append(
                {
                    "device_address": dev.get("address"),
                    "device_alias": dev.get("alias"),
                    "uuid": unwrap(mt, "UUID"),
                    "state": unwrap(mt, "State"),
                    "codec": unwrap(mt, "Codec"),
                    "volume": unwrap(mt, "Volume"),
                }
            )

    print(json.dumps({"battery": battery, "transport": transport}))


if __name__ == "__main__":
    main()
