#pragma once

#include <cstdlib>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>

// The service supplies public and backend origins from the port registry.
// An unmanaged invocation defaults to its own loopback listener only.
class sinnix_http_admission {
    std::set<std::string> origins;
    std::set<std::string> authorities;
    std::set<std::string> response_origins;
    bool reflect_cors;

    static bool valid_origin(const std::string & origin) {
        auto separator = origin.find("://");
        if (separator == std::string::npos ||
            (origin.substr(0, separator) != "http" && origin.substr(0, separator) != "https")) return false;
        auto authority = origin.substr(separator + 3);
        auto colon = authority.rfind(':');
        if (colon == std::string::npos) return false;
        auto host = authority.substr(0, colon);
        if (host != "127.0.0.1" && host != "localhost" && host != "[::1]") return false;
        auto port = authority.substr(colon + 1);
        if (port.empty() || port.size() > 5 || port.find_first_not_of("0123456789") != std::string::npos) return false;
        auto number = std::stoi(port);
        return number > 0 && number <= 65535 && port == std::to_string(number);
    }

    static bool refuse(httplib::Response & response) {
        response.status = 403;
        response.set_header("Connection", "close");
        response.set_content("{\"error\":\"request refused\"}", "application/json");
        return false;
    }

public:
    sinnix_http_admission(int port, bool tls = false, const std::string & cors = "*") {
        reflect_cors = cors == "*" || cors == "localhost";
        std::istringstream cors_input(cors);
        std::string cors_origin;
        while (std::getline(cors_input, cors_origin, ',')) response_origins.insert(cors_origin);
        const char * configured = std::getenv("SINNIX_LLAMA_ALLOWED_ORIGINS");
        if (configured) {
            std::istringstream input(configured);
            std::string origin;
            while (std::getline(input, origin, ',')) {
                if (!valid_origin(origin)) throw std::runtime_error("invalid SINNIX_LLAMA_ALLOWED_ORIGINS");
                origins.insert(origin);
            }
            if (origins.empty() || std::string(configured).back() == ',')
                throw std::runtime_error("empty SINNIX_LLAMA_ALLOWED_ORIGINS entry");
        }
        auto add_listener = [&](const std::string & number, bool encrypted) {
            for (const char * host : {"127.0.0.1", "localhost", "[::1]"}) {
                auto origin = std::string(encrypted ? "https://" : "http://") + host + ":" + number;
                if (!valid_origin(origin)) throw std::runtime_error("invalid llama listener port");
                origins.insert(origin);
            }
        };
        // Router children use private listener ports. Upstream forwards the
        // original Origin and supplies its parent port through this variable.
        add_listener(std::to_string(port), tls);
        if (const char * parent = std::getenv("LLAMA_SERVER_ROUTER_PORT")) {
            add_listener(parent, false);
            add_listener(parent, true);
        }
        for (const auto & origin : origins) authorities.insert(origin.substr(origin.find("://") + 3));
    }

    bool allow(const httplib::Request & request, httplib::Response & response) const {
        if (request.get_header_value_count("Host") != 1 ||
            !authorities.count(request.get_header_value("Host"))) return refuse(response);
        const char * browser_headers[] = {"Origin", "Sec-Fetch-Site", "Sec-Fetch-Mode", "Sec-Fetch-Dest", "Sec-Fetch-User"};
        bool browser = false;
        for (auto name : browser_headers) {
            auto count = request.get_header_value_count(name);
            if (count > 1) return refuse(response);
            browser = browser || count != 0;
        }
        if (request.has_header("Origin")) {
            auto origin = request.get_header_value("Origin");
            if (!origins.count(origin)) return refuse(response);
            // Preserve the upstream CORS option as a response restriction.
            // It cannot broaden the service's trusted request origins.
            if (reflect_cors || response_origins.count(origin))
                response.set_header("Access-Control-Allow-Origin", origin);
            response.set_header("Vary", "Origin");
        } else if (browser) {
            const bool document = (request.method == "GET" || request.method == "HEAD") &&
                request.get_header_value("Sec-Fetch-Mode") == "navigate" &&
                request.get_header_value("Sec-Fetch-Dest") == "document" &&
                request.get_header_value("Sec-Fetch-User") == "?1";
            if (request.get_header_value("Sec-Fetch-Site") != "same-origin" && !document) return refuse(response);
        }
        return true;
    }
};
