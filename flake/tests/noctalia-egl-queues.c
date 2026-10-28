#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef bool EGLBoolean;
#define EGL_TRUE true
#define EGL_FALSE false
struct wl_event_queue { int identity; };
struct wl_surface;
struct wl_proxy { struct wl_event_queue *queue; };
struct wl_buffer { struct wl_proxy proxy; };
struct zwp_linux_dmabuf_v1 { struct wl_proxy proxy; };
struct zwp_linux_buffer_params_v1 { struct wl_proxy proxy; };
typedef struct { struct wl_buffer *buffer; EGLBoolean done; } DmaBufParamsCreateState;
struct zwp_linux_buffer_params_v1_listener {
    void (*created)(void *, struct zwp_linux_buffer_params_v1 *, struct wl_buffer *);
    void (*failed)(void *, struct zwp_linux_buffer_params_v1 *);
};
typedef struct {
    void *wdpy;
    struct { void *syncobj; struct zwp_linux_dmabuf_v1 *dmabuf; } globals;
    struct { struct { struct { struct wl_event_queue *(*display_create_queue_with_name)(void *, const char *); } wl; } *priv; } *platform;
} WlDisplayInstance;
typedef struct { struct wl_event_queue *queue; } WlSwapChain;

static struct wl_event_queue temporary_queue, persistent_queue;
static struct zwp_linux_dmabuf_v1 wrapper;
static struct zwp_linux_buffer_params_v1 params;
static struct wl_buffer buffer;
static const struct zwp_linux_buffer_params_v1_listener *listener;
static void *listener_data;
static int creates, destroys, wrappers_destroyed, params_destroyed, roundtrips, named;
static int failure;

static struct wl_event_queue *wl_display_create_queue(void *display) {
    (void)display; creates++; return failure == 1 ? NULL : &temporary_queue;
}
static struct wl_event_queue *named_queue(void *display, const char *name) {
    assert(strstr(name, "EGLSurface(") == name); named++; return wl_display_create_queue(display);
}
static void wl_event_queue_destroy(struct wl_event_queue *queue) {
    assert(queue == &temporary_queue); destroys++;
}
static void *wl_proxy_create_wrapper(void *object) {
    (void)object; return failure == 2 ? NULL : &wrapper;
}
static void wl_proxy_set_queue(struct wl_proxy *proxy, struct wl_event_queue *queue) { proxy->queue = queue; }
static void wl_proxy_wrapper_destroy(void *object) { assert(object == &wrapper); wrappers_destroyed++; }
static uint32_t wl_proxy_get_id(struct wl_proxy *proxy) { (void)proxy; return 7; }
static struct zwp_linux_buffer_params_v1 *zwp_linux_dmabuf_v1_create_params(struct zwp_linux_dmabuf_v1 *object) {
    params.proxy.queue = object->proxy.queue; return failure == 3 ? NULL : &params;
}
static void zwp_linux_buffer_params_v1_add_listener(struct zwp_linux_buffer_params_v1 *object,
        const struct zwp_linux_buffer_params_v1_listener *callbacks, void *data) {
    assert(object == &params); listener = callbacks; listener_data = data;
}
static void zwp_linux_buffer_params_v1_add(struct zwp_linux_buffer_params_v1 *object,
        int fd, unsigned plane, unsigned offset, unsigned stride, unsigned high, unsigned low) {
    (void)object; (void)fd; (void)plane; (void)offset; (void)stride; (void)high; (void)low;
}
static void zwp_linux_buffer_params_v1_create(struct zwp_linux_buffer_params_v1 *object,
        unsigned width, unsigned height, unsigned fourcc, unsigned flags) {
    (void)object; (void)width; (void)height; (void)fourcc; (void)flags;
}
static void zwp_linux_buffer_params_v1_destroy(struct zwp_linux_buffer_params_v1 *object) {
    assert(object == &params); params_destroyed++;
}
static int wl_display_roundtrip_queue(void *display, struct wl_event_queue *queue) {
    (void)display; assert(queue && queue == params.proxy.queue); roundtrips++;
    if (failure == 4) return -1;
    buffer.proxy.queue = queue;
    if (failure == 5) listener->failed(listener_data, &params);
    else listener->created(listener_data, &params, &buffer);
    return 0;
}
static void created(void *data, struct zwp_linux_buffer_params_v1 *object, struct wl_buffer *result) {
    (void)object; DmaBufParamsCreateState *state = data; state->buffer = result; state->done = true;
}
static void failed(void *data, struct zwp_linux_buffer_params_v1 *object) {
    (void)object; DmaBufParamsCreateState *state = data; state->buffer = NULL; state->done = true;
}
static const struct zwp_linux_buffer_params_v1_listener DMABUF_PARAMS_LISTENER = { created, failed };

/* Both regions below come verbatim from the package source under test. */
#include "queue-source.h"

static void reset(void) {
    creates = destroys = wrappers_destroyed = params_destroyed = roundtrips = named = failure = 0;
    memset(&buffer, 0, sizeof(buffer));
}
int main(void) {
    __typeof__(((WlDisplayInstance *)0)->platform->priv[0]) priv = { .wl.display_create_queue_with_name = named_queue };
    __typeof__(((WlDisplayInstance *)0)->platform[0]) platform = { .priv = &priv };
    struct zwp_linux_dmabuf_v1 dmabuf = {0};
    WlDisplayInstance inst = { .wdpy = &inst, .globals = { .syncobj = &inst, .dmabuf = &dmabuf }, .platform = &platform };
    WlSwapChain swapchain = {0};
    reset();
    if (!queue_policy(&inst, &swapchain, NULL) || swapchain.queue || creates) {
        fputs("explicit synchronization retained a private queue\n", stderr); return 1;
    }
    assert(ShareDmaBuf(&inst, NULL, 1, 1, 1, 4, 0, 0, 0) == &buffer);
    assert(creates == 1 && destroys == 1 && roundtrips == 1);
    assert(params_destroyed == 1 && wrappers_destroyed == 1 && buffer.proxy.queue == NULL);
    for (int fail = 1; fail <= 5; fail++) {
        reset(); failure = fail;
        assert(ShareDmaBuf(&inst, NULL, 1, 1, 1, 4, 0, 0, 0) == NULL);
        assert(creates == 1 && destroys == (fail == 1 ? 0 : 1));
        assert(wrappers_destroyed == (fail <= 2 ? 0 : 1));
        assert(params_destroyed == (fail <= 3 ? 0 : 1));
    }
    reset(); inst.globals.syncobj = NULL;
    assert(queue_policy(&inst, &swapchain, NULL) && swapchain.queue && creates == 1 && named == 1);
    reset();
    assert(ShareDmaBuf(&inst, &persistent_queue, 1, 1, 1, 4, 0, 0, 0) == &buffer);
    assert(creates == 0 && destroys == 0 && buffer.proxy.queue == &persistent_queue);
    reset(); priv.wl.display_create_queue_with_name = NULL;
    assert(queue_policy(&inst, &swapchain, NULL) && creates == 1 && named == 0);
    reset(); failure = 1;
    assert(!queue_policy(&inst, &swapchain, NULL));
    puts("explicit temporary-queue cleanup and implicit persistent-queue cases passed");
}
