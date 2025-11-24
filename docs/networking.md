# Networking Playbook

## Baseline Stack
- `modules/networking.nix` enables NetworkManager + systemd-resolved with pinned DNS resolvers and installs the CLI diagnostics stack (nmap, tcpdump, wireshark, etc.).
- SSH and mosh are available on every host; UDP 60000–61000 is open for mosh.
- Mullvad is optional (desktop only); it remains disconnected until you launch the client.

## Tailscale (Tailnet social graph)
- Service is enabled for all hosts via `services.tailscale.*` in `modules/networking.nix`.
- Firewall trusts `tailscale0`, and routing features are prepped so hosts can both accept incoming Tailscale traffic and publish routes/exit-node functionality later.
- DNS stays under systemd-resolved control (`--accept-dns=false`), avoiding clashes with MagicDNS until explicitly enabled.
- Built-in Tailscale SSH is on (`--ssh`), so every device in the tailnet can shell in without juggling extra keys once approved in the admin console.

### First-time login per host
1. Rebuild to pick up the service: `sudo nix run .#switch` (or `sudo nix run .#test` to dry-run first).
2. Start ```tailscaled``` if it is not already running: `sudo systemctl enable --now tailscaled`.
3. Authenticate: `sudo tailscale up --ssh --accept-dns=false`. The command prints a login URL.
4. Open the URL, choose **Sign in with GitHub**, and authenticate as `Sinity@github`. GitHub/Tailscale treat the email as case-insensitive, so any casing works.
5. Once the CLI shows `Success`, the node appears in the admin console. Repeat on each host/VM.

### Useful follow-ups
- Verify connectivity: `tailscale status` (peer list) and `tailscale ip -4/-6` (assigned addresses).
- Enable reverse shell access from other tailnet nodes: `tailscale serve ssh --hostname <device-name>` or rely on the `--ssh` flag already set.
- If you want a node to behave like a public IP for the rest of the tailnet, consider `tailscale up --advertise-exit-node` (desktop) or `--advertise-routes=0.0.0.0/0,::/0` on the VPS, then approve it in the admin panel.
- Use [Tailscale Funnel](https://tailscale.com/funnel) or a VPS reverse proxy when you need to publish services to the wider internet; the current setup focuses on private tailnet connectivity.

Feel free to expand this file with per-service serve configs or Funnel recipes as they solidify.
