---
name: reverse-engineering
description: Analyze firmware, updater packages, native binaries, encryption routines, and undocumented device protocols with REA, Ghidra, Binwalk, and Unblob on NixOS.
---

# Reverse engineering

Sinnix supplies `rea`, `ghidra`, `ghidra-analyzeHeadless`, `binwalk`,
`unblob`, `7z`, and binutils. REA's wrapper selects the Nix Ghidra/JDK and
absolute extraction-tool paths. Use the CLI in an existing session; the
managed `full` MCP profile exposes `rea mcp` to new agent sessions.

## Establish the artifact

Acquire the vendor's exact model/build package and retain its source URL,
SHA-256, size, and acquisition date with the device dossier. Preserve the
original; extract into a new directory. Private device observations and
analysis stay outside tracked repositories. Use per-task managed scratch for
temporary files and the device's subject home for retained evidence.

Start with `rea --help` and `rea doctor --provider ghidra --json`.
Inspect firmware using `rea inspect-firmware-regions /absolute/image` and
extract explicitly with `rea extract-firmware /absolute/image /new/output`.
Read the complete report, including unsupported formats and missing extractors.
High entropy suggests compression or encryption; it does not distinguish them.

## Choose the loader

REA accepts selected native executable formats, not arbitrary raw flash or
banked 8051 firmware. For a supported executable, inspect `rea analyze --help`
and select `--provider ghidra`. Use direct Ghidra for raw firmware: inspect
`ghidra-analyzeHeadless` usage and available language IDs, then explicitly
select architecture, endianness, base address, loader, and bank mapping.
Record each assumption. Preserve file offsets separately from CPU addresses;
equal addresses in different banks are different code.

Analyze an updater's libraries as well as its payload. Trace container parsing,
length/offset calculations, checksum and signature checks, decryptors, and
device transport. Confirm a reconstructed decoder against independent stored
checksums, vectors, metadata and coherent instructions. A successful round trip
alone can reproduce the same mistake twice. Decompiled C is an interpretation;
settle disputed operations from bytes, assembly and controlled test vectors.

## Test a device hypothesis

Distinguish host idle/DPMS behavior, static-content dimming, content-dependent
power limiting, temperature limiting, and panel maintenance before proposing a
patch. Find the relevant timer/state transitions and their callers rather than
searching for a single brightness constant. Compare stock builds when available.
Treat third-party address maps as hypotheses until matched to the image hash.

Deliver exact image identity, byte ranges, calls and reproductions supporting
each conclusion. Report static findings separately from hardware behavior.
Offline analysis does not authorize flashing, HID/DDC writes, service-menu
changes, or defeating panel protection. Before any firmware write, obtain
explicit authority for the exact image and establish backup, boot validation,
recovery method and consequences of an interrupted update.

Run heavy analysis through a declared AgentCTL operation. Keep target paths
and retained result paths explicit; one analysis owns its temporary project.
Use upstream manuals for current command contracts:

- [REA firmware](https://github.com/morluto/rea/blob/main/docs/firmware-analysis.md)
- [REA providers](https://github.com/morluto/rea/blob/main/docs/installation.md)
- [Ghidra](https://github.com/NationalSecurityAgency/ghidra)
