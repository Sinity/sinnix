"""Admit configured local AI clients before reading bodies or dispatching requests."""
import os
from urllib.parse import urlsplit


class BrowserBoundary:
    def __init__(self, app, *, allowed_ports=None, allowed_hosts=None):
        self.app = app
        self.hosts = {host.lower() for host in allowed_hosts} if allowed_hosts is not None else {"127.0.0.1", "localhost", "::1"}
        if not self.hosts:
            raise ValueError("empty AI listener host set")
        self.ports = set(allowed_ports) if allowed_ports is not None else {
            int(port) for port in os.environ["SINNIX_LITELLM_PORTS"].split(",")
        }
        if not self.ports or any(not 1 <= port <= 65535 for port in self.ports):
            raise ValueError("invalid LiteLLM listener ports")

    def authority(self, value, *, origin=False):
        if not value or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value):
            return None
        try:
            parsed = urlsplit(value if origin else "http://" + value)
            port = parsed.port if parsed.port is not None else 80
            if (parsed.scheme != "http" or parsed.hostname not in self.hosts
                    or port not in self.ports or parsed.username is not None or parsed.password is not None
                    or parsed.path or parsed.query or parsed.fragment):
                return None
            return parsed.hostname, port
        except ValueError:
            return None

    async def __call__(self, scope, receive, send):
        if scope["type"] not in {"http", "websocket"}:
            return await self.app(scope, receive, send)
        fields = {name: [] for name in (
            b"host", b"origin", b"sec-fetch-site", b"sec-fetch-mode", b"sec-fetch-dest", b"sec-fetch-user",
        )}
        for name, value in scope.get("headers", []):
            if name.lower() in fields:
                fields[name.lower()].append(value.decode("latin1"))
        valid = len(fields[b"host"]) == 1 and all(len(values) <= 1 for values in fields.values())
        host = self.authority(fields[b"host"][0]) if valid else None
        valid = valid and host is not None
        if valid and fields[b"origin"]:
            valid = self.authority(fields[b"origin"][0], origin=True) == host
        headers = {name: values[0] for name, values in fields.items() if len(values) == 1}
        browser = any(fields[name] for name in fields if name.startswith(b"sec-fetch-"))
        navigation = (
            scope["type"] == "http" and scope.get("method") in {"GET", "HEAD"}
            and headers.get(b"sec-fetch-mode") == "navigate"
            and headers.get(b"sec-fetch-dest") == "document"
            and headers.get(b"sec-fetch-user") == "?1"
        )
        if browser and not navigation:
            valid = valid and headers.get(b"sec-fetch-site") in {"same-origin", "none"}
        if not valid:
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
            else:
                body = b"browser request origin or host refused"
                await send({"type": "http.response.start", "status": 403, "headers": [
                    (b"content-type", b"text/plain; charset=utf-8"),
                    (b"content-length", str(len(body)).encode()), (b"connection", b"close"),
                ]})
                await send({"type": "http.response.body", "body": body})
            return
        return await self.app(scope, receive, send)
