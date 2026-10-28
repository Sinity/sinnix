/* Redirect only meminfo for earlyoom dry-run checks and the isolated VM. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

FILE *fopen(const char *path, const char *mode)
{
    FILE *(*real_fopen)(const char *, const char *) = dlsym(RTLD_NEXT, "fopen");
    const char *fixture = getenv("EARLYOOM_TEST_MEMINFO");
    if (fixture && strcmp(path, "/proc/meminfo") == 0)
        path = fixture;
    return real_fopen(path, mode);
}
