# sinnix-prime — durable BIOS settings

Settings the operator has applied to the prime motherboard that NixOS
cannot re-apply itself. Recorded here so a BIOS reset (firmware update,
CMOS clear, fTPM purge) does not silently regress performance.

## PCIe — force Gen 2 on the GPU slot

**What**: NVIDIA RTX (sinnix-prime's GPU) was negotiating an unstable
Gen 3 link under sustained load, causing intermittent DMA timeouts under
heavy compute. Pinning the slot to Gen 2 stabilizes the link with
negligible perf cost for the workloads on this host (no scientific
compute that saturates the bus).

**Where**: BIOS → `Advanced` → `PCIe Configuration` → `Slot 1 Link Speed`
(or whichever slot the discrete GPU is in) → `Gen2`.

**Verify after boot**:

```bash
nvidia-smi --query-gpu=pcie.link.gen.current --format=csv
# Expected: pcie.link.gen.current
#           2
```

If it reads `3` post-reset, re-enter BIOS and re-apply.

## CPU — turbo mode setting

**What**: The default turbo policy on this board over-shoots in mixed
workloads (sustained capture + bursty compile), tripping thermal throttle
and causing kernel softlockups in `sinex-source-worker-*` units. The
operator pinned a specific turbo mode that holds frequency below the
unstable peak.

**Where**: BIOS → `Advanced` → `CPU Configuration` → `Intel Turbo Boost
Max Technology 3.0` (and/or `Intel Turbo Boost Technology`) — confirm the
specific toggle with the operator; recorded here as "the turbo setting".

**Verify after boot**:

```bash
cpupower frequency-info | grep -iE 'turbo|boost'
# Expected: boost state support: Supported, Active: yes
# (or the specific value the operator pinned)

# Check actual sustained freq under load:
stress-ng --cpu 16 --timeout 60s &
watch -n 1 'cat /proc/cpuinfo | grep MHz | sort -u'
```

## Re-applying after reset

1. Press `Del` during POST to enter BIOS.
2. Apply the two settings above.
3. Save & exit (`F10`).
   in `seed/` if results differ from expectations.

## Related

- `modules/services/below.nix` continuously records frequency/thermal
  data; gaps in that series after a hardware change are the first signal
  that a BIOS regression has shipped.
  settings being applied (the original investigation seeds + decision
  crystals live there).
