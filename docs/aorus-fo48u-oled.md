# Gigabyte AORUS FO48U — OLED Dimming, Service Mode & Linux Survival Guide

> Citation-backed reference for the 48" 4K 120Hz OLED (LG WOLED panel) on
> sinnix-prime (Hyprland + NVIDIA). Compiled 2026-06-12. Every concrete claim
> carries a source URL. See "Confidence & caveats" for what is vendor-grade vs
> forum hearsay.

---

## TL;DR — what to actually do

1. **Update firmware first.** Verified-latest is **F06 (2022)**, flashed via
   **OSD Sidekick over USB on Windows** (cable direct to PC, no hub). F06
   substantially softened the static-content auto-dimming versus the shipping
   F04 — gradual, often recovers on mouse movement. Biggest no-risk win.
   ([eskerahn](https://eskerahn.dk/?p=4772),
   [Gigabyte support](https://www.gigabyte.com/Monitor/AORUS-FO48U/support))
2. **Stop looking for an OSD toggle — there isn't one.** The FO48U has **no
   "OLED Care," no "Static Control," no "Peak Brightness," no "Pixel Orbit"**
   menu. Those belong to _newer_ Gigabyte QD-OLED models (FO32U2/FO27Q3), not
   this 2022 WOLED panel. RTINGS says the static dimming has "no option to turn
   it off." ([RTINGS](https://www.rtings.com/monitor/reviews/gigabyte/aorus-fo48u-oled),
   [FO48U manual](https://download.gigabyte.com/FileList/Manual/AORUS_FO48U_UM_English_20220214.pdf))
3. **To kill ASBL (static dimming): use the hidden service menu.** Power off +
   unplug ≥15 s → hold joystick **UP** while powering back on → an **"F"**
   appears in the OSD → select it. Booting into service mode largely disables
   the static-content dimming (reports vary: fully off vs. a slow imperceptible
   fade). At-your-own-risk; do **not** touch "Panel Curr"/"Panel SSC."
   ([HardForum p.11](https://hardforum.com/threads/gigabyte-aorus-fo48u-48-4k-120hz-oled.2011874/page-11),
   [Reddit r/OLED_Gaming](https://old.reddit.com/r/OLED_Gaming/comments/uvv8qd/you_can_disable_auto_static_content_dimming/))
4. **For full-screen ABL, lower brightness / tweak contrast.** ABL (brightness
   drop on bright full-field content) is a hardware power-budget limit and
   **cannot** be turned off. Owners reduce visibility with **brightness ~15-25%**
   for desktop, or the "brightness 100 + contrast ~10" trick that "pretty much
   never activates ABL."
   ([HardForum p.7](https://hardforum.com/threads/gigabyte-aorus-fo48u-48-4k-120hz-oled.2011874/page-7))
5. **Linux+NVIDIA: connect via DisplayPort 1.4 (DSC), not HDMI.** Older NVIDIA
   cards can't do 4K120 4:4:4 over HDMI 2.1 on Linux. Cap VRR range to
   ~**60-120 Hz** to avoid the panel's low-refresh gamma-shift/flicker. Expect
   HDR on NVIDIA Wayland to look washed-out/dim — a driver/compositor
   limitation, not the panel; SDR is the saner desktop choice.
   ([Level1Techs](https://forum.level1techs.com/t/rate-7950x3d-4090-with-a-aorus-fo48u-monitor/197322),
   [Arch BBS](https://bbs.archlinux.org/viewtopic.php?id=295188))
6. **No custom firmware exists** for the FO48U or its panel. Don't chase it.
   (`gofirmware.com` is a scam aggregator — avoid.)

---

## 1. Service / diagnostic / factory menu access

**Exact entry sequence (FO48U-confirmed, multiple users):**

> 1. Power monitor off and unplug the power cord. Leave it off and unplugged
>    for at least 15 seconds.
> 2. While holding the **UP** direction on the joystick on the bottom of the
>    monitor, plug back in the power cord and power on the monitor with the
>    remote (or push the joystick button down while keeping it held up if you
>    don't have the remote handy).
> 3. Open the OSD — if you see an **"F"** in the corner of the OSD, you are in
>    service mode. Open the service menu by navigating to and selecting the "F".

Source: [HardForum p.11](https://hardforum.com/threads/gigabyte-aorus-fo48u-48-4k-120hz-oled.2011874/page-11)
re-confirming the original [Reddit r/OLED_Gaming post](https://old.reddit.com/r/OLED_Gaming/comments/uvv8qd/you_can_disable_auto_static_content_dimming/).
A generic shorter version ("hold joystick up while plugging in power, navigate
to F") is documented for all Aorus monitors on
[Blur Busters](https://forums.blurbusters.com/viewtopic.php?t=9230).
_(Minor source discrepancy: text says the "F" is top-right; the menu overlay
itself renders top-left.)_

**Remote:** the FO48U ships with an IR remote, used to trigger power-on while
joystick-up is held. There is **no remote key-code combo** — entry is purely the
hardware power-on + joystick-up.

**What the service menu exposes (only first-hand FO48U account on record):**

- **Energy** mode — ERC / CEC / STD (STD = highest brightness)
- **Flicker** — a grey test rectangle
- **Pattern** — full-screen test patterns: White, R, G, B, Black
- **Panel Curr** (panel current) — function undocumented
- **Panel SSC** — function undocumented

Source: [HardForum p.11](https://hardforum.com/threads/gigabyte-aorus-fo48u-48-4k-120hz-oled.2011874/page-11).

**The actual reason people use it:** booting into service mode disables (or
heavily softens) the **ASBL/ASC static-content dimming** — the desktop
annoyance. The full-screen **ABL is not removed** (hardware limit). Service mode
persists across sleep/resume but is lost on a full power-off (re-enter it).

**Is this the "diagnostics mode"?** Almost certainly — it's the only hidden mode
on the FO48U, and its headline effect is killing static dimming.

**Risk:** no FO48U "I bricked it" report surfaced, but the menu exposes
panel-current/voltage-class parameters (Panel Curr/SSC) with unknown effects. On
any OLED these are the classic way to wreck calibration or stress the panel —
**look, don't blindly change.** General LG-panel warning: a wrong
backlight/voltage or white-balance value can permanently damage color/brightness
([soft4led](https://www.soft4led.com/lg-tv-service-menu-codes/)).

**Non-applicability:** the FO48U uses an LG _panel_ but **Gigabyte's own
scaler/firmware/OSD — not LG webOS.** So all the famous **LG TV service codes**
(EZ-Adjust/In-Start, passwords `0000`/`0413`, the `RCR312WR` service remote) **do
not apply.** The LG-level OLED compensation cycle and ~2000h pixel-refresh do run
on the FO48U, but they're firmware-automatic and not manually controllable from
Gigabyte's service menu in any documented way.

---

## 2. OLED dimming mechanisms on this panel

Authoritative reference:
[TFTCentral — "OLED dimming confusion: APL, ABL, ASBL, TPC and GSR explained"](https://tftcentral.co.uk/articles/oled-dimming-confusion-apl-abl-asbl-tpc-and-gsr-explained).

| Mechanism                                                                                   | Trigger                                                                     | Dims static desktop?                                             | Disableable on FO48U?                                                |
| ------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- | ---------------------------------------------------------------- | -------------------------------------------------------------------- |
| **ABL** (Automatic Brightness Limiter)                                                      | High APL — bright full-screen content. Instant. Panel power-budget physics. | No (minimal on dark desktop)                                     | **No** — hardware, never disableable on any OLED                     |
| **ASBL / TPC** (Automatic Static Brightness Limiter = LG's Temporal Peak Luminance Control) | Static/unchanging image; dims whole panel over a few minutes                | **Yes — this is the annoying one**                               | **Not via OSD.** Only via service menu (or softened by F06 firmware) |
| **GSR** (Global Sticky Reduction)                                                           | Small static regions (logos/UI); dims _just those areas_                    | Localized only (taskbars/persistent UI)                          | Not cleanly; subtle by design                                        |
| **APL** (Average Picture Level)                                                             | —                                                                           | n/a — it's the _measurement_ ABL/TPC read, not a dimming feature | n/a                                                                  |

- **ASBL and TPC are the same mechanism** — TFTCentral states LG implements ASBL
  as "Temporal Peak Luminance Control (TPC)." This produces the FO48U's measured
  ~30%-dim-after-5-min / 50%-after-10-min / black-at-15-min behavior.
  ([TFTCentral](https://tftcentral.co.uk/articles/oled-dimming-confusion-apl-abl-asbl-tpc-and-gsr-explained),
  [TechSpot](https://www.techspot.com/review/2345-gigabyte-aorus-fo48u-oled/))
- The **"GSR = per-pixel/cumulative" framing is NOT** how TFTCentral defines it —
  they describe small-static-_region_ dimming, not a cumulative usage counter.
  Treat the cumulative interpretation as community speculation.
- **Static vs full-screen split:** ASBL/TPC dims **static content** (desktop
  problem); ABL dims **bright full-screen content** (HDR-highlights problem).
  Independent mechanisms.
- TFTCentral notes purpose-built _desktop_ OLED monitors (LG 32EP950, Dell
  AW3423DW) ship _without_ TPC/ASBL — TV-panel-derived monitors like the FO48U
  inherit it.

---

## 3. OSD settings that affect dimming

**Critical correction:** most settings often named — "OLED Care," "Static
Control," "Peak Brightness," "Pixel Orbit," "APL Stabilize," "Dark Boost,"
"Uniform Brightness" — **do not exist on the FO48U.** They are Gigabyte's 2024+
QD-OLED "OLED Care" feature set (FO32U2/FO27Q3). Anyone telling you to "enable
Static Control" on an FO48U is describing a different monitor.
([FO32U2 manual p.10](https://www.manualowl.com/m/Gigabyte/AORUS-FO32U2/Manual/729620?page=10),
[Gigabyte OLED Care](https://www.gigabyte.com/WebPage/1077/),
[FO48U manual](https://download.gigabyte.com/FileList/Manual/AORUS_FO48U_UM_English_20220214.pdf))

**What the FO48U OSD actually has:**

- **Gaming:** Aim Stabilizer (BFI strobing), **Black Equalizer** (shadow lift;
  10 = neutral true-black), Super Resolution, Adaptive-Sync toggle. No
  "Overdrive" (OLED needs none).
  ([digitalmasta](https://digitalmasta.com/gigabyte-aorus-fo48u-gaming-monitor-review/),
  [Tom's Hardware](https://www.tomshardware.com/reviews/gigabyte-aorus-fo48u))
- **Picture:** Brightness, Contrast, Sharpness, Gamma, Color Temperature,
  Picture Modes (incl. HDR modes when HDR10 detected).
  ([FO48U manual](https://www.manualowl.com/m/Gigabyte/AORUS-FO48U/Manual/642815?page=36))
- **No "Dark Boost"** — the shadow control is **Black Equalizer**. **No "Uniform
  Brightness."**

**Recommended static-desktop OSD settings (FO48U-specific):**

- **Firmware:** latest (≥ **F06**) — biggest single lever.
- **Brightness:** ~**15-25%** (owners cite ~15%) — smaller, less-visible ABL
  swings + lower burn-in risk.
- **Contrast:** near default ~50; _or_ the "brightness 100 + contrast ~10" trick
  to dodge the ABL ceiling while keeping the OSD bright.
- **Black Equalizer:** **10** (neutral) for true blacks.
- **Color Temperature:** nudge RGB down slightly if ABL on bright pages bothers
  you (lowers peak nits).
- **Picture Mode:** **Standard/Green** (Green is accurate out-of-box); **avoid
  HDR for static desktop** — HDR makes ABL far more aggressive.

Sources: [HardForum p.7](https://hardforum.com/threads/gigabyte-aorus-fo48u-48-4k-120hz-oled.2011874/page-7),
[eskerahn](https://eskerahn.dk/?p=4772),
[RTINGS](https://www.rtings.com/monitor/reviews/gigabyte/aorus-fo48u-oled),
[TechSpot](https://www.techspot.com/review/2345-gigabyte-aorus-fo48u-oled/).

---

## 4. Firmware

**Official source:**
[gigabyte.com/Monitor/AORUS-FO48U/support](https://www.gigabyte.com/Monitor/AORUS-FO48U/support).
The page currently surfaces only the **OSD Sidekick tool** (`B22.0607.1`,
Jun 23 2022) — firmware is pushed _through_ Sidekick over USB rather than offered
as a standalone F-file download.

**Version history (community-verified; not a complete official changelog):**
shipped on **F04**; **F02** early-stable; **F05 (beta)** — _"Optimize the
brightness performance in HDR mode"_; **F06** (mid-2022) — **highest version
verifiable from real sources.** Could not confirm any F07+. Check OSD Sidekick's
in-app updater for the true current build.

**What updates changed:**

- **Dimming:** F06 substantially improved static auto-dimming — gradual, often
  recovers on mouse movement (vs. abrupt F04). Full-field ABL unchanged
  (hardware). ([eskerahn](https://eskerahn.dk/?p=4772))
- **VRR/G-Sync:** F05-beta changed EDID VRR floor 40→24 Hz, causing NVIDIA
  black-screen/out-of-range below ~50 Hz, and **broke G-Sync** (black screen on
  adaptive-sync engage) — users reverted to F02 or used **CRU** to raise the
  floor back to ≥40 Hz.
  ([HardForum p.7](https://hardforum.com/threads/gigabyte-aorus-fo48u-48-4k-120hz-oled.2011874/page-7))
- **HDR:** F05 claims HDR brightness optimization; one F06 user lost
  HDR-certification reporting in Windows, others fine — inconsistent.
- **Aim Stabilizer (BFI):** later firmware enabled strobing at 60/80/90 Hz.

**How it's flashed (exact):** **Windows-only.** Connect PC↔monitor with the
**USB Type-B upstream cable**, run the firmware EXE / OSD Sidekick. Gotchas:
**plug USB direct into the PC** (hubs/extensions cause mid-flash failure); **keep
the screen active** (move mouse) so protection dimming doesn't interrupt;
flashing **resets settings and scrambles Windows display arrangement**. **No
USB-stick-into-monitor method exists.**
([eskerahn](https://eskerahn.dk/?p=4772),
[Reddit step-by-step](https://www.reddit.com/r/OLED_Gaming/comments/poe3ey/update_aorus_fo48u_firmware_stepbystep/),
[HardForum p.7](https://hardforum.com/threads/gigabyte-aorus-fo48u-48-4k-120hz-oled.2011874/page-7))

> **Linux note:** the flash tool is Windows-only — use a Windows machine or a VM
> with USB passthrough. No source documents a Linux flash path.

**Custom / community firmware — honest answer: NONE EXISTS.** GitHub search for
`FO48U` returns zero repositories
([search](https://github.com/search?q=FO48U+firmware&type=repositories)). The
openlgtv/webOS rooting projects are for LG _TVs_ and irrelevant (FO48U runs
Gigabyte's scaler, not webOS — [openlgtv](https://openlgtv.github.io/)). The only
"mods" are the built-in service menu (kills ASBL), CRU EDID edits
(VRR/G-Sync/flicker), and OSD contrast tricks (ABL). **Avoid `gofirmware.com`** —
SEO scam serving Android ROMs.

---

## 5. HDR/SDR brightness behavior on Linux

FO48U-specific Linux reports are sparse — most coverage is Windows/macOS. Below
combines FO48U panel behavior (OS-agnostic) with NVIDIA-Wayland-wide issues that
_will_ apply.

- **Use DisplayPort 1.4 (DSC), not HDMI.** NVIDIA's proprietary Linux driver
  historically couldn't do 4K120 4:4:4 over HDMI 2.1 (HDMI Forum blocked the
  open implementation) — you got 4:2:0 with banding/blurry text. Driver
  **580.95.05 added YCbCr 4:2:2**, but full FRL needs Blackwell (RTX 50-series).
  DP 1.4 sidesteps this.
  ([UbuntuHandbook](https://ubuntuhandbook.org/index.php/2025/10/nvidia-580-95-05-added-ycbcr-422-support-for-linux/),
  [Arch BBS](https://bbs.archlinux.org/viewtopic.php?id=295188),
  [Level1Techs](https://forum.level1techs.com/t/rate-7950x3d-4090-with-a-aorus-fo48u-monitor/197322))
- **VRR floor / gamma-shift:** the FO48U flickers and gamma-shifts below ~50 Hz.
  Cap the VRR range to ~**60-120 Hz** (wide enough for LFC).
  ([Tom's Hardware](https://www.tomshardware.com/reviews/gigabyte-aorus-fo48u),
  [HardForum p.7](https://hardforum.com/threads/gigabyte-aorus-fo48u-48-4k-120hz-oled.2011874/page-7))
- **HDR on NVIDIA Wayland = washed-out and/or too dim** (general, applies here):
  the egl-wayland Colorspace property bug leaves `NV_INPUT_COLORSPACE = None` even
  when PQ/BT2020 is signaled ([egl-wayland #108](https://github.com/NVIDIA/egl-wayland/issues/108));
  KWin caps HDR at SDR brightness on some setups (Plasma 6.1 added brightness
  sliders — [KDE discuss](https://discuss.kde.org/t/hdr-mode-too-dim-when-displaying-hdr-content/41790),
  [zamundaaa](https://zamundaaa.github.io/wayland/2024/05/11/more-hdr-and-color.html)).
  The FO48U is also a _modest-brightness_ HDR panel. **For a static desktop, run
  SDR.**
- **VRR flicker on Hyprland/NVIDIA generally:** aggressive refresh switching +
  backlight flashing with `vrr 1/2`; OpenGL-via-Xwayland flicker on 545/550 (fix:
  force zink or use native Wayland apps).
  ([Hyprland #4436](https://github.com/hyprwm/Hyprland/issues/4436),
  [NVIDIA forums](https://forums.developer.nvidia.com/t/opengl-xwayland-insane-flickering/283087))
- **Known-good OSD combos (OS-agnostic, apply to Linux):** SDR "Green" mode
  accurate out-of-box at ~50% brightness; "contrast 10 + brightness 100"
  reportedly "pretty much never activates ABL." Contrast does digital
  black-crush; brightness dims the actual OLED circuitry.
  ([HardForum p.7](https://hardforum.com/threads/gigabyte-aorus-fo48u-48-4k-120hz-oled.2011874/page-7))

**Practical sinnix-prime recipe:** DisplayPort 1.4 → cap VRR ~60-120 Hz → SDR
Green mode ~50% (or lower for desktop) → expect HDR-on-Wayland washout as a
driver issue, not a defect → service-menu to kill ASBL if static dimming bugs
you.

---

## 6. Pragmatic mitigations (no service menu)

- **Firmware F06** — softens static dimming the most, zero risk.
- **Low brightness (15-25%)** — shrinks ABL swings + cuts burn-in risk.
- **"Brightness 100 + contrast ~10"** — owner trick that avoids triggering ABL
  while keeping the OSD bright.
- **Keep content non-static:** the static dimmer recovers instantly on
  window/mouse movement. A subtle moving wallpaper, a cursor-jiggle/anti-idle
  utility, or normal interaction resets the timer.
  ([TechSpot](https://www.techspot.com/review/2345-gigabyte-aorus-fo48u-oled/))
- **OS-side habits (the FO48U has no anti-burn-in toggles, so these do that
  job):** dark mode + dark wallpaper, **auto-hide taskbar/panels** (avoids GSR
  logo-dimming + burn-in on persistent UI), short screen-off/DPMS timeout,
  screensaver, periodic wallpaper rotation.
- **CRU EDID edits** to set a sane VRR floor (≥40-60 Hz) — fixes low-refresh
  flicker and the F05 G-Sync black-screen without firmware downgrade.

---

## Confidence & caveats

**Well-documented (vendor/review-grade):**

- ABL/ASBL/TPC/GSR mechanism definitions and the **ASBL = TPC identity**
  ([TFTCentral](https://tftcentral.co.uk/articles/oled-dimming-confusion-apl-abl-asbl-tpc-and-gsr-explained)).
- ABL is hardware and **cannot be disabled**; the FO48U has **no OSD toggle** for
  static dimming ([RTINGS](https://www.rtings.com/monitor/reviews/gigabyte/aorus-fo48u-oled)).
- The "OLED Care / Static Control / Peak Brightness" menu is a **different, newer
  Gigabyte model** — verified against FO48U + FO32U2 manuals.
- Firmware flashes **via OSD Sidekick over USB, Windows-only**; **no custom
  firmware exists** (zero GitHub repos).
- NVIDIA HDMI 2.1 4K120 limitation on Linux and HDR-Wayland washout are
  documented driver/compositor issues.

**Forum hearsay / community-reported (credible, multi-user, not vendor-confirmed):**

- The **service-menu access sequence** and its menu contents — one detailed
  first-hand FO48U account (HardForum p.11) corroborated by the generic Aorus
  method (Blur Busters) and the original Reddit post.
- **Whether service mode fully kills ASBL or only softens it** — users
  _disagree_. Expect "much better," not necessarily "perfectly off."
- Specific owner OSD numbers (15% brightness, contrast-10 trick) are
  _preferences_, not calibrated standards.
- **"Latest firmware = F06"** — verified from community sources; could not fully
  enumerate Gigabyte's current list (page surfaces only OSD Sidekick), so a newer
  build may exist — check Sidekick's in-app updater.

**Sourcing limits:** HardForum pages return HTTP 403 to automated fetching, so
several owner-quote details came via search-index excerpts rather than full-page
reads — worth confirming in a browser. FO48U-specific _Linux_ HDR/Hyprland
reports are essentially absent; those findings are general NVIDIA-Wayland issues
extrapolated to this panel and labeled as such.

> **Do not change `Panel Curr` / `Panel SSC` in the service menu** — undocumented
> panel-current/voltage parameters; the realistic way to permanently damage the
> panel.
