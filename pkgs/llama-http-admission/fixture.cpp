#include <cpp-httplib/httplib.h>
#include "admission.h"
#include <atomic>
#include <iostream>

int main(int argc, char ** argv) {
    if (argc != 2) return 2;
    int port = std::stoi(argv[1]);
    try {
        const char * cors = std::getenv("FIXTURE_CORS_ORIGINS");
        sinnix_http_admission policy(port, false, cors ? cors : "*");
        httplib::Server server;
        std::atomic<int> calls{0};
        server.new_task_queue = [] { return new httplib::ThreadPool(2); };
        server.set_pre_routing_handler([&](const httplib::Request & request, httplib::Response & response) {
            return policy.allow(request, response) ? httplib::Server::HandlerResponse::Unhandled : httplib::Server::HandlerResponse::Handled;
        });
        server.Get("/v1/models", [&](const httplib::Request &, httplib::Response & response) {
            ++calls;
            response.set_content("{\"data\":[]}", "application/json");
        });
        server.Get("/count", [&](const httplib::Request &, httplib::Response & response) {
            response.set_content(std::to_string(calls.load()), "text/plain");
        });
        server.Post("/v1/models", [&](const httplib::Request & request, httplib::Response & response) {
            ++calls;
            response.set_content(request.body, "application/json");
        });
        server.Options("/v1/models", [](const httplib::Request &, httplib::Response & response) {
            response.set_content("", "text/plain");
        });
        server.Get("/stream", [&](const httplib::Request &, httplib::Response & response) {
            response.set_chunked_content_provider("text/event-stream", [](size_t, httplib::DataSink & sink) {
                sink.write("data: fixture\n\n", 15);
                sink.done();
                return true;
            });
        });
        return server.listen("127.0.0.1", port) ? 0 : 1;
    } catch (const std::exception & error) {
        std::cerr << error.what() << '\n';
        return 2;
    }
}
