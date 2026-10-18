# The native monitor exposes connection/account metadata with wildcard CORS.
# Keep this in the receiver so there is no unguarded backend or second proxy.
# recheck: drop when nixpkgs NATS monitoring enforces listener authorities and
# browser-origin/Fetch Metadata admission before handlers without wildcard CORS.
_: _final: prev: {
  nats-server = prev.nats-server.overrideAttrs (old: {
    patches = (old.patches or [ ]) ++ [ ./nats-monitor-admission.patch ];
    postPatch = (old.postPatch or "") + ''
      cp ${./nats-monitor-http.go} server/sinnix-monitor-http.go
    '';
  });
}
