set -euo pipefail

# Args (all supplied by capture-peripherals.nix's ExecStart, all Nix store
# paths or config values -- never user input):
#   $1 capture_bin      sinnix-capture CLI
#   $2 capture_root     local lane root, .../captures/peripherals
#   $3 parse_bluez_py    store path to parse_bluez.py
#   $4 parse_solaar_py   store path to parse_solaar.py
capture_bin="$1"
capture_root="$2"
parse_bluez_py="$3"
parse_solaar_py="$4"

# Logitech: solaar has no machine-readable output mode, so `solaar show`'s
# text is parsed by anchoring on the "Codename" line every real device
# emits (receivers alone, and empty paired slots, never have one) and
# taking the next Battery: line in that block -- see parse_solaar.py.
# A missing/unpaired receiver is a legitimate empty result, not a failure:
# solaar exits 0 with zero devices if nothing is plugged in.
logitech_json="$(solaar show 2>/dev/null | python3 "$parse_solaar_py")"
echo "$logitech_json" | "$capture_bin" write --capture-root "$capture_root" --lane logitech

# Bluetooth: one ObjectManager call returns bluez's entire live object tree
# (devices, GATT battery service exposed via org.bluez.Battery1 once
# Experimental=true, and AVRCP media transports) -- cheaper and more robust
# than walking the D-Bus tree path by path. An empty battery[] array is
# expected whenever no paired device is currently connected in range (a
# closed earbuds case does not advertise); that is a device-presence fact,
# not a lane failure, so it is still a normal envelope, not an error exit.
bluez_json="$(busctl call org.bluez / org.freedesktop.DBus.ObjectManager GetManagedObjects --json=short |
  python3 "$parse_bluez_py")"
echo "$bluez_json" | jq '.battery' | "$capture_bin" write --capture-root "$capture_root" --lane bt-battery
echo "$bluez_json" | jq '.transport' | "$capture_bin" write --capture-root "$capture_root" --lane bt-audio
