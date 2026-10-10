{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      sources = import ../data/agent-cli-sources.nix { inherit pkgs; };
    in
    {
      checks.pi-recovery-integrity =
        pkgs.runCommand "pi-recovery-integrity-check" { nativeBuildInputs = [ pkgs.python3 ]; }
          ''
            python3 - ${sources."@earendil-works/pi-coding-agent"} ${
              sources."@earendil-works/pi-coding-agent".original
            } <<'PY'
            import base64, json, sys, tarfile
            with tarfile.open(sys.argv[1]) as archive:
                lock = json.load(archive.extractfile("package/npm-shrinkwrap.json"))
                package = json.load(archive.extractfile("package/package.json"))
            with tarfile.open(sys.argv[2]) as original, tarfile.open(sys.argv[1]) as repaired:
                assert original.getnames() == repaired.getnames()
                before = json.load(original.extractfile("package/npm-shrinkwrap.json"))
                changed = []
                for name in before["packages"]:
                    a, b = before["packages"][name], lock["packages"][name]
                    if a != b:
                        assert not a.get("integrity")
                        assert {key: value for key, value in b.items() if key != "integrity"} == a
                        changed.append(name)
                assert len(changed) == 5
                for entry in original.getmembers():
                    other = repaired.getmember(entry.name)
                    assert (entry.type, entry.mode, entry.uid, entry.gid, entry.mtime, entry.linkname) == (other.type, other.mode, other.uid, other.gid, other.mtime, other.linkname)
                    if entry.isfile() and entry.name != "package/npm-shrinkwrap.json":
                        assert original.extractfile(entry).read() == repaired.extractfile(other).read()
            assert package["name"] == "@earendil-works/pi-coding-agent"
            assert package["version"] == "0.87.1"
            dependencies = {name: entry for name, entry in lock["packages"].items() if name}
            assert len(dependencies) == 143
            for entry in dependencies.values():
                assert entry["resolved"].startswith("https://registry.npmjs.org/")
                algorithm, digest = entry["integrity"].split("-", 1)
                assert algorithm == "sha512"
                assert len(base64.b64decode(digest, validate=True)) == 64
            print("143 recovery dependency acquisitions have full SHA-512 integrity")
            PY
            touch "$out"
          '';
    };
}
