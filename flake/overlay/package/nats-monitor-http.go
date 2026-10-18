package server

import (
	"net"
	"net/http"
	"net/url"
	"strconv"
	"strings"
)

// sinnixMonitoringHandler protects monitoring, not the authenticated NATS
// protocol. Listener identity supplies the port; configured/native loopback
// names supply authorities. No machine-specific address table is duplicated.
func sinnixMonitoringHandler(next http.Handler, configuredHost string, address *net.TCPAddr, scheme string) http.Handler {
	normalize := func(host string) string {
		if ip := net.ParseIP(host); ip != nil {
			return ip.String()
		}
		return strings.TrimSuffix(strings.ToLower(host), ".")
	}
	hosts := map[string]bool{"localhost": true, "127.0.0.1": true, "::1": true}
	if ip := net.ParseIP(configuredHost); ip == nil || !ip.IsUnspecified() {
		if configuredHost != "" {
			hosts[normalize(configuredHost)] = true
		}
	}
	if address.IP != nil && !address.IP.IsUnspecified() {
		hosts[address.IP.String()] = true
	}
	allowedAuthority := func(authority string) bool {
		if authority == "" || strings.ContainsAny(authority, "/\\?#@ \t\r\n") || strings.HasSuffix(authority, ":") {
			return false
		}
		u, err := url.Parse(scheme + "://" + authority)
		if err != nil || u.User != nil || !hosts[normalize(u.Hostname())] {
			return false
		}
		port := 80
		if scheme == "https" {
			port = 443
		}
		if u.Port() != "" {
			port, err = strconv.Atoi(u.Port())
		}
		return err == nil && port == address.Port
	}
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		refuse := func() {
			// Do not drain a declared but unfinished body before refusing it.
			r.Close = true
			w.Header().Set("Connection", "close")
			http.Error(w, "monitoring request refused", http.StatusForbidden)
		}
		if !allowedAuthority(r.Host) {
			refuse()
			return
		}
		origin := ""
		if values := r.Header.Values("Origin"); len(values) != 0 {
			if len(values) != 1 {
				refuse()
				return
			}
			origin = values[0]
			u, err := url.Parse(origin)
			if err != nil || u.Scheme != scheme || origin != scheme+"://"+u.Host || !allowedAuthority(u.Host) {
				refuse()
				return
			}
		}
		metadata := make(map[string]string)
		for _, name := range []string{"Sec-Fetch-Site", "Sec-Fetch-Mode", "Sec-Fetch-Dest", "Sec-Fetch-User"} {
			if values := r.Header.Values(name); len(values) != 0 {
				if len(values) != 1 || values[0] == "" {
					refuse()
					return
				}
				metadata[name] = values[0]
			}
		}
		if len(metadata) != 0 {
			site := metadata["Sec-Fetch-Site"]
			if site != "none" && site != "same-origin" && site != "same-site" && site != "cross-site" {
				refuse()
				return
			}
			mode := metadata["Sec-Fetch-Mode"]
			if mode != "" && mode != "cors" && mode != "no-cors" && mode != "navigate" && mode != "same-origin" && mode != "websocket" {
				refuse()
				return
			}
			user := metadata["Sec-Fetch-User"]
			if user != "" && (user != "?1" || mode != "navigate") {
				refuse()
				return
			}
			navigation := (r.Method == http.MethodGet || r.Method == http.MethodHead) &&
				mode == "navigate" && metadata["Sec-Fetch-Dest"] == "document" && user == "?1"
			if (site == "cross-site" || site == "same-site") && origin == "" && !navigation {
				refuse()
				return
			}
		}
		w.Header().Add("Vary", "Origin")
		w.Header().Set("Cache-Control", "no-store")
		w.Header().Set("X-Content-Type-Options", "nosniff")
		if origin != "" {
			w.Header().Set("Access-Control-Allow-Origin", origin)
		}
		next.ServeHTTP(w, r)
	})
}
