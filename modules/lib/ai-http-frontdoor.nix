# Render the HTTP boundary before the private systemd activation socket.
{ lib }:
{
  publicEndpoint,
  backendEndpoint,
  socketPath,
  browserRequests ? "loopback",
}:
let
  publicPort = lib.last (lib.splitString ":" publicEndpoint);
  # A Unix-socket backend has no TCP authority of its own.
  backendPorts = lib.optional (!lib.hasPrefix "/" backendEndpoint) (
    lib.last (lib.splitString ":" backendEndpoint)
  );
  publicHost = lib.head (lib.splitString ":" publicEndpoint);
  authorities = lib.concatMap (
    port:
    map (host: "${host}:${port}") [
      "127.0.0.1"
      "localhost"
      "[::1]"
    ]
  ) (lib.unique ([ publicPort ] ++ backendPorts));
  origins = map (authority: "http://${authority}") authorities;
  browserHeaders = [
    "Origin"
    "Sec-Fetch-Site"
    "Sec-Fetch-Mode"
    "Sec-Fetch-Dest"
    "Sec-Fetch-User"
  ];
  present = header: "header({'${header}': ['*']})";
in
assert publicHost == "127.0.0.1";
''
  http://:${publicPort} {
    bind ${publicHost}
    route {
      ${lib.optionalString (browserRequests == "native-only") ''
        @browserDenied expression ${lib.concatMapStringsSep " || " present browserHeaders}
        header @browserDenied Connection close
        respond @browserDenied "native requests required" 403
      ''}
      @badHost expression !({http.request.hostport} in ${builtins.toJSON authorities})
      header @badHost Connection close
      respond @badHost "unknown host refused" 403

      # Placeholders join repeated values with commas. Refuse ambiguous
      # browser headers before matching any individually trusted value.
      @repeated expression ${
        lib.concatMapStringsSep " || " (
          header: "{http.request.header.${header}}.contains(',')"
        ) browserHeaders
      }
      header @repeated Connection close
      respond @repeated "ambiguous browser metadata refused" 403

      @badOrigin {
        header Origin *
        not expression {http.request.header.Origin} in ${builtins.toJSON origins}
      }
      header @badOrigin Connection close
      respond @badOrigin "cross-origin request refused" 403

      @badFetch {
        not header Origin *
        expression ${lib.concatMapStringsSep " || " present browserHeaders}
        not header Sec-Fetch-Site same-origin
        not {
          method GET HEAD
          header Sec-Fetch-Mode navigate
          header Sec-Fetch-Dest document
          header Sec-Fetch-User ?1
        }
      }
      header @badFetch Connection close
      respond @badFetch "cross-site request refused" 403

      reverse_proxy unix/${socketPath} {
        flush_interval -1
        # A pooled upstream connection would keep socket-proxyd alive after
        # the last request and extend the backend's declared idle window.
        transport http {
          keepalive off
        }
      }
    }
  }
''
