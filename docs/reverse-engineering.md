# Firmware and binary analysis

The development workbench installs REA 6.2.0, Ghidra, Binwalk, Unblob,
binutils and 7-Zip through Nix. `rea` supplies the Ghidra/JDK and firmware
extractor paths, including Nix's `prlimit` location. It uses locked npm
dependencies and performs no agent setup or package-manager installation at
runtime. Unblob uses a scoped Python 3.13 / setuptools 80 dependency repair.
Its Partclone dependency omits the NILFS copier, which fails against the pinned
headers; the `info` and `restore` tools used for extraction remain available.
Btrfs-stream extraction is unverified on this host: its upstream integration
test fails with `EXDEV` during a sandboxed directory rename. That single case
is excluded from the package build; the sandbox remains enabled.

The `reverse-engineering` skill owns the investigation workflow. REA is
registered in the `full` MCP profile; existing sessions can use its CLI.
Restart an agent using that profile to obtain its MCP tools.

Run bounded analysis as declared work:

```sh
agentctl job start sinnix firmware_analysis -- inspect-firmware-regions /absolute/image.bin --json
agentctl job start sinnix firmware_analysis -- extract-firmware /absolute/image.bin /absolute/new-output --json
agentctl job start sinnix firmware_analysis -- decompile /absolute/program function_name --provider ghidra --json
agentctl job start sinnix ghidra_analysis -- /absolute/project-directory Project -import /absolute/image.bin -loader BinaryLoader -processor <verified-language-id>
agentctl job start sinnix reverse_engineering_verify
```

The last operation checks tool readiness, known gzip extraction bytes, real
ELF function decompilation and unchanged source digests. Fixtures are generated
in managed scratch and removed after the check. It does not test a device.

REA's firmware support does not include a raw flash loader or banked 8051
analysis. Use direct Ghidra with an evidenced processor and bank mapping for
those inputs. A scanner signature or plausible decompilation is insufficient
to establish a correct load map or a hardware behavior.

Firmware research is offline by default. Firmware writes require a separate
decision about the exact candidate, backup, boot integrity checks and a
demonstrated recovery path. Device artifacts and private findings belong in
the device dossier and its Beads task, outside this public repository.
