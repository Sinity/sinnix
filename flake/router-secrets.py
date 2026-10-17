"""Inject deployment secrets into the declared shell quoting contexts."""

import re
import sys
from pathlib import Path


def inject(script: Path, wifi_file: Path, mac_file: Path, key_file: Path) -> None:
    values = []
    for label, path in [
        ("WiFi PSK", wifi_file),
        ("sinnix-prime MAC", mac_file),
        ("router SSH authorization", key_file),
    ]:
        try:
            value = path.read_text().rstrip("\r\n")
        except OSError:
            raise ValueError(f"{label} is missing or unreadable") from None
        if not value or any(c in value for c in "\r\n\0"):
            raise ValueError(f"{label} must contain one nonempty line")
        values.append(value)
    wifi, mac, key = values
    if not re.fullmatch(r"[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}", mac):
        raise ValueError("sinnix-prime MAC is invalid")
    if not key.startswith(("ssh-ed25519 ", "ssh-rsa ", "ecdsa-sha2-")):
        raise ValueError("router SSH authorization must be an OpenSSH public key")
    # UCI assignments are single quoted; post-configuration key commands use
    # double quotes. Preserve data rather than interpreting shell/sed syntax.
    single_quoted_wifi = wifi.replace("'", "'\"'\"'")
    double_quoted_key = re.sub(r'([\\"$`])', r"\\\1", key)
    replacements = [
        ("@@WIFI_PSK@@", 3, single_quoted_wifi),
        ("@@SINNIX_PRIME_MAC@@", 1, mac),
        ("@@ROUTER_AUTHORIZED_KEY@@", 2, double_quoted_key),
    ]
    text = script.read_text()
    for marker, count, _value in replacements:
        if text.count(marker) != count:
            raise ValueError(f"router template marker count changed: {marker}")
    # One substitution pass prevents marker-shaped secret bytes from being
    # mistaken for a second template input.
    mapping = {marker: value for marker, _count, value in replacements}
    text = re.sub("|".join(map(re.escape, mapping)), lambda m: mapping[m[0]], text)
    script.write_text(text)
    script.chmod(0o600)


if __name__ == "__main__":
    try:
        inject(*(Path(arg) for arg in sys.argv[1:]))
    except ValueError as exc:
        print(f"router-deploy: {exc}", file=sys.stderr)
        sys.exit(66)
