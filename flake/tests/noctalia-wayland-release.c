#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/socket.h>
#include <unistd.h>
#include <wayland-client.h>

static void release_event(struct wl_display *display, int server, struct wl_proxy *buffer) {
    const uint32_t message[] = { wl_proxy_get_id(buffer), 8U << 16 };
    assert(wl_display_prepare_read(display) == 0);
    assert(write(server, message, sizeof(message)) == sizeof(message));
    assert(wl_display_read_events(display) == 0);
}
int main(void) {
    int sockets[2];
    assert(socketpair(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0, sockets) == 0);
    struct wl_display *display = wl_display_connect_to_fd(sockets[0]);
    assert(display);
    struct wl_event_queue *queue = wl_display_create_queue(display);
    struct wl_proxy *buffer = wl_proxy_create((struct wl_proxy *)display, &wl_buffer_interface);
    assert(queue && buffer);
    /* No listener: explicit synchronization ignores wl_buffer.release. */
    wl_proxy_set_queue(buffer, queue);
    release_event(display, sockets[1], buffer);
    assert(wl_display_dispatch_pending(display) == 0);
    assert(wl_display_dispatch_queue_pending(display, queue) == 1);
    assert(wl_display_dispatch_queue_pending(display, queue) == 0);
    wl_proxy_set_queue(buffer, NULL);
    wl_event_queue_destroy(queue);
    release_event(display, sockets[1], buffer);
    assert(wl_display_dispatch_pending(display) == 1);
    assert(wl_display_dispatch_pending(display) == 0);
    wl_proxy_destroy(buffer);
    wl_display_disconnect(display);
    close(sockets[1]);
    puts("ignored releases drain on private and default queues without a listener");
}
