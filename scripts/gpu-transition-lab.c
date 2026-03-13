#define _POSIX_C_SOURCE 200809L

#include <GLFW/glfw3.h>
#include <GL/gl.h>

#include <math.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

typedef struct {
  int seconds;
  int busy_ms;
  int idle_ms;
  int width;
  int height;
  int fullscreen;
  int swap_interval;
} options_t;

static double now_seconds(void) {
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return (double)ts.tv_sec + (double)ts.tv_nsec / 1000000000.0;
}

static void sleep_millis(long millis) {
  struct timespec req = {
      .tv_sec = millis / 1000,
      .tv_nsec = (millis % 1000) * 1000000L,
  };
  nanosleep(&req, NULL);
}

static int parse_int_arg(const char *flag, const char *value) {
  char *end = NULL;
  long parsed = strtol(value, &end, 10);
  if (end == value || *end != '\0') {
    fprintf(stderr, "%s requires an integer, got: %s\n", flag, value);
    exit(2);
  }
  return (int)parsed;
}

static void parse_size_arg(const char *value, int *width, int *height) {
  if (sscanf(value, "%dx%d", width, height) != 2 || *width <= 0 || *height <= 0) {
    fprintf(stderr, "--size requires WIDTHxHEIGHT, got: %s\n", value);
    exit(2);
  }
}

static options_t parse_args(int argc, char **argv) {
  options_t opts = {
      .seconds = 120,
      .busy_ms = 4000,
      .idle_ms = 2500,
      .width = 1920,
      .height = 1080,
      .fullscreen = 0,
      .swap_interval = 0,
  };

  for (int i = 1; i < argc; ++i) {
    if (strcmp(argv[i], "--seconds") == 0) {
      if (++i >= argc) {
        fprintf(stderr, "--seconds requires a value\n");
        exit(2);
      }
      opts.seconds = parse_int_arg("--seconds", argv[i]);
    } else if (strcmp(argv[i], "--busy-ms") == 0) {
      if (++i >= argc) {
        fprintf(stderr, "--busy-ms requires a value\n");
        exit(2);
      }
      opts.busy_ms = parse_int_arg("--busy-ms", argv[i]);
    } else if (strcmp(argv[i], "--idle-ms") == 0) {
      if (++i >= argc) {
        fprintf(stderr, "--idle-ms requires a value\n");
        exit(2);
      }
      opts.idle_ms = parse_int_arg("--idle-ms", argv[i]);
    } else if (strcmp(argv[i], "--size") == 0) {
      if (++i >= argc) {
        fprintf(stderr, "--size requires a value\n");
        exit(2);
      }
      parse_size_arg(argv[i], &opts.width, &opts.height);
    } else if (strcmp(argv[i], "--fullscreen") == 0) {
      opts.fullscreen = 1;
    } else if (strcmp(argv[i], "--vsync") == 0) {
      opts.swap_interval = 1;
    } else if (strcmp(argv[i], "--help") == 0 || strcmp(argv[i], "-h") == 0) {
      printf("gpu-transition-lab\n");
      printf("Usage: gpu-transition-lab [--seconds N] [--busy-ms N] [--idle-ms N] [--size WxH] [--fullscreen] [--vsync]\n");
      exit(0);
    } else {
      fprintf(stderr, "Unknown argument: %s\n", argv[i]);
      exit(2);
    }
  }

  if (opts.seconds <= 0 || opts.busy_ms <= 0 || opts.idle_ms <= 0) {
    fprintf(stderr, "seconds, busy-ms, and idle-ms must all be positive\n");
    exit(2);
  }

  return opts;
}

static void render_frame(double t, int width, int height, bool busy_phase) {
  float phase = (float)t;
  float bg_r = 0.05f + 0.35f * (0.5f + 0.5f * sinf((float)(phase * 0.8)));
  float bg_g = 0.08f + 0.30f * (0.5f + 0.5f * sinf((float)(phase * 1.1)));
  float bg_b = busy_phase ? 0.18f : 0.06f;

  glViewport(0, 0, width, height);
  glClearColor(bg_r, bg_g, bg_b, 1.0f);
  glClear(GL_COLOR_BUFFER_BIT);

  glMatrixMode(GL_PROJECTION);
  glLoadIdentity();
  glOrtho(-1.0, 1.0, -1.0, 1.0, -1.0, 1.0);

  glMatrixMode(GL_MODELVIEW);
  glLoadIdentity();
  glRotatef((float)(fmod(t * 90.0, 360.0)), 0.0f, 0.0f, 1.0f);

  int loops = busy_phase ? 400 : 4;
  for (int i = 0; i < loops; ++i) {
    float scale = 0.15f + 0.75f * ((float)i / (float)loops);
    glBegin(GL_TRIANGLES);
    glColor3f(1.0f - scale, 0.3f + 0.5f * scale, 0.2f + 0.6f * scale);
    glVertex2f(0.0f, 0.75f * scale);
    glColor3f(0.2f + 0.6f * scale, 1.0f - scale, 0.35f + 0.4f * scale);
    glVertex2f(-0.75f * scale, -0.65f * scale);
    glColor3f(0.2f + 0.6f * scale, 0.25f + 0.5f * scale, 1.0f - scale);
    glVertex2f(0.75f * scale, -0.65f * scale);
    glEnd();
  }

  glFinish();
}

int main(int argc, char **argv) {
  options_t opts = parse_args(argc, argv);

  if (!glfwInit()) {
    fprintf(stderr, "glfwInit failed\n");
    return 1;
  }

  glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 2);
  glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 1);
  glfwWindowHint(GLFW_DOUBLEBUFFER, GLFW_TRUE);

  GLFWmonitor *monitor = NULL;
  if (opts.fullscreen) {
    monitor = glfwGetPrimaryMonitor();
  }

  GLFWwindow *window = glfwCreateWindow(opts.width, opts.height, "gpu-transition-lab", monitor, NULL);
  if (window == NULL) {
    fprintf(stderr, "glfwCreateWindow failed\n");
    glfwTerminate();
    return 1;
  }

  glfwMakeContextCurrent(window);
  glfwSwapInterval(opts.swap_interval);

  printf("gpu-transition-lab: seconds=%d busy_ms=%d idle_ms=%d size=%dx%d fullscreen=%d vsync=%d\n",
         opts.seconds, opts.busy_ms, opts.idle_ms, opts.width, opts.height, opts.fullscreen, opts.swap_interval);
  fflush(stdout);

  double started = now_seconds();
  double busy_for = (double)opts.busy_ms / 1000.0;
  double idle_for = (double)opts.idle_ms / 1000.0;
  double cycle_for = busy_for + idle_for;
  int last_phase = -1;
  double last_report = started;

  while (!glfwWindowShouldClose(window)) {
    double t = now_seconds();
    double elapsed = t - started;
    if (elapsed >= (double)opts.seconds) {
      break;
    }

    double cycle_pos = fmod(elapsed, cycle_for);
    bool busy_phase = cycle_pos < busy_for;
    int phase = busy_phase ? 1 : 0;
    if (phase != last_phase) {
      printf("gpu-transition-lab: t=%.3f phase=%s\n", elapsed, busy_phase ? "busy" : "idle");
      fflush(stdout);
      last_phase = phase;
    }

    int width = opts.width;
    int height = opts.height;
    glfwGetFramebufferSize(window, &width, &height);
    render_frame(elapsed, width, height, busy_phase);
    glfwSwapBuffers(window);
    glfwPollEvents();

    if (!busy_phase) {
      sleep_millis(25);
    }

    if (t - last_report >= 1.0) {
      printf("gpu-transition-lab: t=%.3f width=%d height=%d\n", elapsed, width, height);
      fflush(stdout);
      last_report = t;
    }
  }

  glfwDestroyWindow(window);
  glfwTerminate();
  return 0;
}
