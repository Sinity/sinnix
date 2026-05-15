# Netgear R6220 — OpenWrt 24.10.5 (ramips/mt7621)
# Declarative router configuration for sinnix-gw.
#
# Deploy with: nix run .#router-deploy
#
# === Design goals ===
# - Full network authority: DHCP, DoH-upstream DNS, static leases, NTP server
# - WiFi: WPA3/WPA2-mixed, both bands, EU regulatory domain (PL)
# - DNS-over-HTTPS: Cloudflare via https-dns-proxy, dnsmasq as local cache
# - Adblock: adblock-fast DNS-level blocking for all LAN devices
# - SQM: fq_codel at 270 Mbps (90% of 300M WAN, fq_codel chosen over CAKE for
#   MT7621 CPU budget — CAKE caps at ~100-150 Mbps on this SoC)
# - UPnP/NAT-PMP: auto port-forwarding for gaming/P2P
# - Bandwidth monitoring: nlbwmon per-device traffic stats
# - Firewall: strict WAN reject, port-forward for Transmission
# - Zero manual UI interaction after first deploy
#
# === Hardware constraints ===
# MT7621ST: dual-thread MIPS 1004Kc @ 880MHz, 128MB RAM, 128MB NAND
# - SQM + flow_offloading are MUTUALLY EXCLUSIVE (offloaded flows bypass qdiscs)
# - CAKE is too CPU-heavy at >150 Mbps; fq_codel is ~2x lighter
# - AdGuard Home too RAM-heavy; adblock-fast uses ~2-3MB
#
# === Secrets ===
# WiFi PSK lives in agenix (secret/wifi-psk.age).
# The deploy script injects it at runtime from /run/agenix/wifi-psk.
# To create: echo -n 'your-psk' | agenix -e secret/wifi-psk.age

{ lib }:

let
  openwrtLib = import ../../modules/lib/openwrt.nix { inherit lib; };
  inherit (openwrtLib) mkSection;

  # ========================
  # Topology constants
  # ========================
  lanSubnet = "192.168.1";
  lanGateway = "${lanSubnet}.1";
  lanNetmask = "255.255.255.0";
  dhcpStart = 50; # .50 – .199 dynamic range (leaves .1-.49 for static)
  dhcpLimit = 150;

  # ========================
  # Static DHCP leases
  # ========================
  staticLeases = [
    {
      name = "sinnix-prime";
      mac = "@@SINNIX_PRIME_MAC@@";
      ip = "${lanSubnet}.10";
      # Desktop gets a low static IP; easy to remember, easy to firewall
    }
  ];

  # ========================
  # Authorized SSH key
  # ========================
  authorizedKey = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDwD8IB2eVfw6X7z9AqBBGjrqOIOCJ4tden1we7mCqOy sinity@sinnix-prime";

  # ========================
  # WiFi
  # ========================
  wifi = {
    ssid_2g = "sinnix-gw"; # 2.4 GHz SSID
    ssid_5g = "sinnix-gw-5g"; # 5 GHz SSID
    # WPA3-SAE + WPA2-PSK mixed for broad compatibility
    psk = "@@WIFI_PSK@@";
    country = "PL"; # Regulatory domain (Poland, EU)
  };

  # ========================
  # WAN / Uplink
  # ========================
  # ISP plan: ~300 Mbps down, ~100-150 Mbps up.
  # SQM target set to 85-90% of line speed so the qdisc stays in control.
  wan = {
    downloadMbit = 270; # 90% of 300
    uploadMbit = 120; # ~85% of ~140 (typical upload)
    interface = "wan"; # OpenWrt interface name
  };

  # ========================
  # Port forwards
  # ========================
  portForwards = [
    {
      name = "transmission-tcp";
      src = "wan";
      dest = "lan";
      destIp = "${lanSubnet}.10"; # sinnix-prime
      proto = "tcp";
      destPort = "51413";
      srcDport = "51413";
    }
    {
      name = "transmission-udp";
      src = "wan";
      dest = "lan";
      destIp = "${lanSubnet}.10";
      proto = "udp";
      destPort = "51413";
      srcDport = "51413";
    }
  ];

in
{
  # ============================================================
  # Router metadata (used by flake/router.nix)
  # ============================================================
  hostname = "sinnix-gw";
  address = lanGateway;
  sshUser = "root";
  inherit authorizedKey;

  # ============================================================
  # Extra opkg packages to install on the router
  # ============================================================
  packages = [
    # DNS-over-HTTPS proxy: Cloudflare upstream, local dnsmasq integration
    "https-dns-proxy"
    "luci-app-https-dns-proxy"

    # SQM / fq_codel: bufferbloat control on WAN
    # (fq_codel chosen over CAKE — CAKE caps at ~100-150 Mbps on MT7621)
    "sqm-scripts"
    "luci-app-sqm"

    # DNS-level ad blocking — lightweight, auto-updating blocklists
    # adblock-fast: dnsmasq-based, available in standard OpenWrt repos (unlike adblock-lean)
    "adblock-fast"
    "luci-app-adblock-fast"

    # UPnP/NAT-PMP: auto port-forwarding for gaming/P2P clients
    # Must use -nftables variant — OpenWrt 24.10 uses fw4 (nftables, not iptables)
    "miniupnpd-nftables"
    "luci-app-upnp"

    # Per-device bandwidth monitoring
    "nlbwmon"
    "luci-app-nlbwmon"

    # Better IRQ balancing on the dual-core MT7621
    "irqbalance"

    # Useful diagnostics
    "tcpdump"
    "bind-dig"
  ];

  # ============================================================
  # UCI configuration (rendered to shell by mkUciScript)
  # ============================================================
  uci = {

    # ----------------------------------------------------------
    # system
    # ----------------------------------------------------------
    system = {
      system = mkSection "system" {
        hostname = "sinnix-gw";
        timezone = "CET-1CEST,M3.5.0,M10.5.0/3"; # Europe/Warsaw
        ttylogin = false;
        log_size = 512;
        log_file = "/overlay/log/syslog"; # Persist logs across reboots (NAND overlay)
        urandom_seed = false;
        compat_version = "1.1";
      };

      ntp = mkSection "timeserver" {
        enabled = true;
        enable_server = true; # Act as NTP server for the LAN
        server = [
          "time.cloudflare.com"
          "0.pool.ntp.org"
          "1.pool.ntp.org"
        ];
      };

      # WAN LED: netdev trigger
      led_wan = mkSection "led" {
        name = "wan";
        sysfs = "green:wan";
        trigger = "netdev";
        mode = "link tx rx";
        dev = "wan";
      };
    };

    # ----------------------------------------------------------
    # network
    # ----------------------------------------------------------
    network = {
      loopback = mkSection "interface" {
        device = "lo";
        proto = "static";
        ipaddr = "127.0.0.1";
        netmask = "255.0.0.0";
      };

      globals = mkSection "globals" {
        ula_prefix = "fdee:a6eb:b0a3::/48"; # keep existing ULA prefix
        packet_steering = true;
      };

      br_lan_dev = mkSection "device" {
        name = "br-lan";
        type = "bridge";
        ports = [
          "lan1"
          "lan2"
          "lan3"
          "lan4"
        ];
      };

      lan = mkSection "interface" {
        device = "br-lan";
        proto = "static";
        ipaddr = lanGateway;
        netmask = lanNetmask;
        ip6assign = 60;
      };

      wan = mkSection "interface" {
        device = "wan";
        proto = "dhcp";
      };

      wan6 = mkSection "interface" {
        device = "wan";
        proto = "dhcpv6";
      };
    };

    # ----------------------------------------------------------
    # wireless
    # ----------------------------------------------------------
    wireless = {
      # 2.4 GHz radio — MT7603
      radio0 = mkSection "wifi-device" {
        type = "mac80211";
        path = "1e140000.pcie/pci0000:00/0000:00:02.0/0000:02:00.0";
        band = "2g";
        channel = "auto";
        htmode = "HT40";
        country = wifi.country;
        disabled = false;
        # Disable legacy 802.11b rates for performance
        legacy_rates = false;
      };

      default_radio0 = mkSection "wifi-iface" {
        device = "radio0";
        network = "lan";
        mode = "ap";
        ssid = wifi.ssid_2g;
        encryption = "sae-mixed"; # WPA3-SAE + WPA2-PSK
        key = wifi.psk;
        ieee80211r = true; # 802.11r fast BSS transition
        ft_over_ds = false;
        ft_psk_generate_local = true;
        mobility_domain = "1a2b";
      };

      # 5 GHz radio — MT76x2
      radio1 = mkSection "wifi-device" {
        type = "mac80211";
        path = "1e140000.pcie/pci0000:00/0000:00:00.0/0000:01:00.0";
        band = "5g";
        channel = "auto";
        htmode = "VHT80"; # 802.11ac 80 MHz
        country = wifi.country;
        disabled = false;
        legacy_rates = false;
      };

      default_radio1 = mkSection "wifi-iface" {
        device = "radio1";
        network = "lan";
        mode = "ap";
        ssid = wifi.ssid_5g;
        encryption = "sae-mixed";
        key = wifi.psk;
        ieee80211r = true;
        ft_over_ds = false;
        ft_psk_generate_local = true;
        mobility_domain = "1a2b";
      };
    };

    # ----------------------------------------------------------
    # dhcp (dnsmasq + odhcpd)
    # ----------------------------------------------------------
    dhcp = {
      dnsmasq = mkSection "dnsmasq" {
        domainneeded = true;
        boguspriv = true;
        filterwin2k = false;
        localise_queries = true;
        rebind_protection = true;
        rebind_localhost = true;
        local = "/lan/";
        domain = "lan";
        expandhosts = true;
        nonegcache = false;
        cachesize = 4096;
        authoritative = true;
        readethers = true;
        leasefile = "/tmp/dhcp.leases";
        # Let https-dns-proxy handle upstream; dnsmasq queries both DoH proxies
        resolvfile = "";
        noresolv = true;
        server = [
          "127.0.0.1#5053" # Cloudflare DoH (primary)
          "127.0.0.1#5054" # Quad9 DoH (fallback)
        ];
        # Block DNS rebind attacks and private IP leakage
        stop_dns_rebind = true;
        rebind_localhost_ok = true;
        nonwildcard = true;
        localservice = true;
        ednspacket_max = 1232;
        # Local search domain pushes .lan names
        local_ttl = 60;
      };

      lan = mkSection "dhcp" {
        interface = "lan";
        start = dhcpStart;
        limit = dhcpLimit;
        leasetime = "12h";
        dhcpv4 = "server";
        dhcpv6 = "server";
        ra = "server";
        ra_slaac = true;
        ra_flags = [
          "managed-config"
          "other-config"
        ];
        # Advertise router as NTP server + DNS to DHCP clients
        dhcp_option = [
          "42,${lanGateway}" # option 42 = NTP server
          "6,${lanGateway}" # option 6 = DNS server (ensures all clients use router DNS)
        ];
      };

      wan = mkSection "dhcp" {
        interface = "wan";
        ignore = true;
      };

      odhcpd = mkSection "odhcpd" {
        maindhcp = false;
        leasefile = "/tmp/hosts/odhcpd";
        leasetrigger = "/usr/sbin/odhcpd-update";
        loglevel = 4;
      };
    }
    # Merge in static DHCP lease sections
    // builtins.listToAttrs (
      map (lease: {
        name = "host_${builtins.replaceStrings [ "-" "." ] [ "_" "_" ] lease.name}";
        value = mkSection "host" {
          name = lease.name;
          mac = lease.mac;
          ip = lease.ip;
          dns = true; # Also register in dnsmasq as <name>.lan
        };
      }) staticLeases
    );

    # ----------------------------------------------------------
    # firewall
    # ----------------------------------------------------------
    firewall = {
      defaults = mkSection "defaults" {
        syn_flood = true;
        input = "REJECT";
        output = "ACCEPT";
        forward = "REJECT";
        # NOTE: flow_offloading DISABLED — it conflicts with SQM.
        # Offloaded flows bypass qdiscs entirely, making SQM useless.
        # If SQM is ever disabled, re-enable these for maximum throughput.
        flow_offloading = false;
        flow_offloading_hw = false;
      };

      zone_lan = mkSection "zone" {
        name = "lan";
        network = [ "lan" ];
        input = "ACCEPT";
        output = "ACCEPT";
        forward = "ACCEPT";
      };

      zone_wan = mkSection "zone" {
        name = "wan";
        network = [
          "wan"
          "wan6"
        ];
        input = "REJECT";
        output = "ACCEPT";
        forward = "REJECT";
        masq = true;
        mtu_fix = true;
      };

      fwd_lan_wan = mkSection "forwarding" {
        src = "lan";
        dest = "wan";
      };

      # --- Standard WAN input rules (keep from default) ---
      rule_dhcp_renew = mkSection "rule" {
        name = "Allow-DHCP-Renew";
        src = "wan";
        proto = "udp";
        dest_port = "68";
        target = "ACCEPT";
        family = "ipv4";
      };

      rule_ping = mkSection "rule" {
        name = "Allow-Ping";
        src = "wan";
        proto = "icmp";
        icmp_type = "echo-request";
        family = "ipv4";
        target = "ACCEPT";
      };

      rule_igmp = mkSection "rule" {
        name = "Allow-IGMP";
        src = "wan";
        proto = "igmp";
        family = "ipv4";
        target = "ACCEPT";
      };

      rule_dhcpv6 = mkSection "rule" {
        name = "Allow-DHCPv6";
        src = "wan";
        proto = "udp";
        dest_port = "546";
        family = "ipv6";
        target = "ACCEPT";
      };

      rule_mld = mkSection "rule" {
        name = "Allow-MLD";
        src = "wan";
        proto = "icmp";
        src_ip = "fe80::/10";
        icmp_type = [
          "130/0"
          "131/0"
          "132/0"
          "143/0"
        ];
        family = "ipv6";
        target = "ACCEPT";
      };

      rule_icmpv6_in = mkSection "rule" {
        name = "Allow-ICMPv6-Input";
        src = "wan";
        proto = "icmp";
        icmp_type = [
          "echo-request"
          "echo-reply"
          "destination-unreachable"
          "packet-too-big"
          "time-exceeded"
          "bad-header"
          "unknown-header-type"
          "router-solicitation"
          "neighbour-solicitation"
          "router-advertisement"
          "neighbour-advertisement"
        ];
        limit = "1000/sec";
        family = "ipv6";
        target = "ACCEPT";
      };

      rule_icmpv6_fwd = mkSection "rule" {
        name = "Allow-ICMPv6-Forward";
        src = "wan";
        dest = "*";
        proto = "icmp";
        icmp_type = [
          "echo-request"
          "echo-reply"
          "destination-unreachable"
          "packet-too-big"
          "time-exceeded"
          "bad-header"
          "unknown-header-type"
        ];
        limit = "1000/sec";
        family = "ipv6";
        target = "ACCEPT";
      };
    }
    # Merge in port forward rules
    // builtins.listToAttrs (
      map (pf: {
        name = "redirect_${builtins.replaceStrings [ "-" "." ] [ "_" "_" ] pf.name}";
        value = mkSection "redirect" {
          name = pf.name;
          src = pf.src;
          dest = pf.dest;
          dest_ip = pf.destIp;
          proto = pf.proto;
          dest_port = pf.destPort;
          src_dport = pf.srcDport;
          target = "DNAT";
        };
      }) portForwards
    );

    # ----------------------------------------------------------
    # sqm — Smart Queue Management (fq_codel)
    # fq_codel is ~2x lighter than CAKE on MIPS and handles 300 Mbps
    # where CAKE would cap at ~100-150 Mbps on this MT7621 SoC.
    # Set to 90% of line speed so the qdisc stays in control of the queue.
    # ----------------------------------------------------------
    sqm = {
      wan_qos = mkSection "queue" {
        enabled = true;
        interface = wan.interface;
        qdisc = "fq_codel";
        script = "simple.qos"; # fq_codel uses simple.qos, not piece_of_cake
        linklayer = "ethernet";
        overhead = 0; # Direct cable (no PPPoE); set to 44 if behind PPPoE
        download = wan.downloadMbit * 1000; # kbps
        upload = wan.uploadMbit * 1000;
        # ECN: signal congestion via marking instead of dropping — helps under CGNAT
        ingress_ecn = "ECN";
        egress_ecn = "ECN";
      };
    };

    # ----------------------------------------------------------
    # UPnP / NAT-PMP — automatic port forwarding
    # Allows gaming, P2P, and VoIP to open ports as needed.
    # LAN-only, no external control interface.
    # ----------------------------------------------------------
    upnpd = {
      config = mkSection "upnpd" {
        enabled = true;
        enable_natpmp = true;
        enable_upnp = true;
        secure_mode = true; # Only allow UPnP from LAN devices
        log_output = false;
        internal_iface = "lan";
        external_iface = "wan";
        # Limit port range for safety
        ext_ports_start = 1024;
        ext_ports_end = 65535;
      };
    };

    # ----------------------------------------------------------
    # nlbwmon — per-device bandwidth monitoring
    # Accessible via LuCI → Statistics → Bandwidth Monitor
    # ----------------------------------------------------------
    nlbwmon = {
      nlbwmon = mkSection "nlbwmon" {
        enabled = true;
        database_interval = 30; # Save every 30s
        database_directory = "/overlay/nlbwmon"; # Must persist across reboots (not tmpfs)
        database_generations = 10;
        protocol_database = "/usr/share/nlbwmon/protocols";
        # Track LAN subnet
        local_network = "${lanSubnet}.0/24";
      };
    };

  }; # end uci

  # ============================================================
  # Post-UCI shell commands (run after uci commit + service reload)
  # These are idempotent setup steps that can't be expressed in UCI.
  # ============================================================
  postCommands = ''
        # Install authorized SSH key for passwordless deploy
        mkdir -p /etc/dropbear
        AUTHKEYS=/etc/dropbear/authorized_keys
        if ! grep -qF "${authorizedKey}" "$AUTHKEYS" 2>/dev/null; then
          echo "${authorizedKey}" >> "$AUTHKEYS"
          chmod 600 "$AUTHKEYS"
          echo "✓ SSH authorized key installed."
        else
          echo "✓ SSH authorized key already present."
        fi

        # Harden Dropbear: disable password auth (key-only), LAN-only
        uci set dropbear.@dropbear[0].PasswordAuth='off'
        uci set dropbear.@dropbear[0].RootPasswordAuth='off'
        uci set dropbear.@dropbear[0].Interface='lan'
        uci commit dropbear
        /etc/init.d/dropbear restart 2>/dev/null || true
        echo "✓ Dropbear hardened: key-only auth, LAN-only."

        # Configure https-dns-proxy: primary (Cloudflare) + fallback (Quad9)
        # dnsmasq queries both via server list; first responder wins
        if [ -f /etc/config/https-dns-proxy ]; then
          # Remove any anonymous defaults
          while uci -q get https-dns-proxy.@https-dns-proxy[-1] >/dev/null 2>&1; do
            uci -q delete https-dns-proxy.@https-dns-proxy[-1]
          done

          # Primary: Cloudflare DoH on port 5053
          uci set https-dns-proxy.cloudflare=https-dns-proxy
          uci set https-dns-proxy.cloudflare.bootstrap_dns='1.1.1.1,1.0.0.1'
          uci set https-dns-proxy.cloudflare.resolver_url='https://cloudflare-dns.com/dns-query'
          uci set https-dns-proxy.cloudflare.listen_addr='127.0.0.1'
          uci set https-dns-proxy.cloudflare.listen_port='5053'

          # Fallback: Quad9 DoH on port 5054
          uci set https-dns-proxy.quad9=https-dns-proxy
          uci set https-dns-proxy.quad9.bootstrap_dns='9.9.9.9,149.112.112.112'
          uci set https-dns-proxy.quad9.resolver_url='https://dns.quad9.net/dns-query'
          uci set https-dns-proxy.quad9.listen_addr='127.0.0.1'
          uci set https-dns-proxy.quad9.listen_port='5054'

          uci commit https-dns-proxy
          /etc/init.d/https-dns-proxy enable 2>/dev/null || true
          /etc/init.d/https-dns-proxy restart 2>/dev/null || /etc/init.d/https-dns-proxy start 2>/dev/null || true
          echo "✓ DoH configured: Cloudflare (5053) + Quad9 fallback (5054)."
        fi

        # Kernel tuning: increase conntrack table (default 15360 is too low for UPnP/P2P)
        echo 32768 > /proc/sys/net/netfilter/nf_conntrack_max 2>/dev/null || true

        # TCP performance: enable Fast Open on both client + server side
        echo 3 > /proc/sys/net/ipv4/tcp_fastopen 2>/dev/null || true

        # Persist sysctl tweaks across reboots (IPv4 + IPv6 hardening)
        cat > /etc/sysctl.d/99-sinnix.conf << 'SYSCTL_EOF'
    # sinnix-gw kernel tuning (managed by nix deploy)
    net.netfilter.nf_conntrack_max = 32768
    net.ipv4.tcp_fastopen = 3
    # IPv6 hardening
    net.ipv6.conf.all.accept_redirects = 0
    net.ipv6.conf.default.accept_redirects = 0
    SYSCTL_EOF
        sysctl -p /etc/sysctl.d/99-sinnix.conf 2>/dev/null || true

        # Setup adblock-fast with blocklists
        if [ -x /etc/init.d/adblock-fast ]; then
          uci set adblock-fast.config=adblock-fast
          uci set adblock-fast.config.enabled='1'
          uci set adblock-fast.config.dns='dnsmasq.servers'
          # Clear existing sources and add curated blocklists
          uci -q delete adblock-fast.config.allowed_domain 2>/dev/null || true
          uci -q delete adblock-fast.config.blocked_domain 2>/dev/null || true
          # Hagezi Pro: comprehensive ad/tracker/malware blocklist
          uci add_list adblock-fast.config.blocked_domain='https://cdn.jsdelivr.net/gh/hagezi/dns-blocklists@latest/dnsmasq/pro.txt'
          # AdGuard DNS filter: mainstream ad blocking
          uci add_list adblock-fast.config.blocked_domain='https://adguardteam.github.io/AdGuardSDNSFilter/Filters/filter.txt'
          uci commit adblock-fast
          /etc/init.d/adblock-fast enable 2>/dev/null || true
          /etc/init.d/adblock-fast restart 2>/dev/null || true
          echo "✓ adblock-fast configured with Hagezi Pro + AdGuard blocklists."
        fi

        # Restart services to apply new config
        /etc/init.d/system reload
        /etc/init.d/network reload
        /etc/init.d/dnsmasq restart
        /etc/init.d/firewall reload
        # irqbalance: enable in UCI config + start daemon
        uci -q set irqbalance.irqbalance.enabled=1
        uci commit irqbalance
        /etc/init.d/irqbalance enable 2>/dev/null || true
        /etc/init.d/irqbalance start 2>/dev/null || true

        # Clean stale miniupnpd iptables firewall include (left over from -iptables variant)
        uci -q delete firewall.miniupnpd 2>/dev/null || true
        uci commit firewall 2>/dev/null || true
        if [ -f /etc/init.d/https-dns-proxy ]; then
          /etc/init.d/https-dns-proxy enable
          /etc/init.d/https-dns-proxy start
        fi
        if [ -f /etc/init.d/sqm ]; then
          /etc/init.d/sqm enable
          /etc/init.d/sqm start
        fi
        if [ -f /etc/init.d/miniupnpd ]; then
          /etc/init.d/miniupnpd enable 2>/dev/null || true
          /etc/init.d/miniupnpd start 2>/dev/null || true
          echo "✓ UPnP/NAT-PMP enabled."
        fi
        if [ -f /etc/init.d/nlbwmon ]; then
          /etc/init.d/nlbwmon enable 2>/dev/null || true
          /etc/init.d/nlbwmon start 2>/dev/null || true
          echo "✓ nlbwmon bandwidth monitoring enabled."
        fi
        # Create persistent directories on NAND overlay
        mkdir -p /overlay/log /overlay/nlbwmon

        # WAN connectivity watchdog: auto-reconnect if DHCP/WAN drops
        mkdir -p /etc/cron.d
        cat > /etc/cron.d/wan-watchdog << 'CRON_EOF'
    # Ping 1.1.1.1 every 5 minutes; reconnect WAN on failure
    */5 * * * * root ping -c 1 -W 5 1.1.1.1 >/dev/null 2>&1 || (logger -t wan-watchdog "WAN down, reconnecting..."; ifup wan)
    CRON_EOF
        /etc/init.d/cron enable 2>/dev/null || true
        /etc/init.d/cron restart 2>/dev/null || true
        echo "✓ WAN watchdog cron installed."

        # Reload wifi last (may briefly disconnect)
        wifi reload
        echo "✓ All services reloaded. Router configuration complete."
  '';
}
