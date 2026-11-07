#ifndef CNTRU_PUBLICATION_DRIVER_H
#define CNTRU_PUBLICATION_DRIVER_H
#define _GNU_SOURCE
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/random.h>
#include <sys/resource.h>
#include <sched.h>
#include <time.h>

#define POOL 256
#define KEYS 8
static uint8_t messages[POOL][64];
static volatile uint64_t checksum;
static uint64_t rng_calls, rng_bytes;
static void need(int ok, const char *where) {
    if (!ok) { fprintf(stderr, "benchmark check failed: %s\n", where); exit(2); }
}
#include "pmu_cycles.h"
static void observe(const void *p, size_t n) {
    __asm__ __volatile__("" : : "r"(p), "r"(n) : "memory");
    checksum += ((const uint8_t *)p)[n - 1];
}
static int os_random(void *ctx, uint8_t *out, size_t n) {
    (void)ctx; rng_calls++; rng_bytes += n;
    while (n) {
        ssize_t r = getrandom(out, n, 0);
        if (r < 0 && errno == EINTR) continue;
        if (r <= 0) return -1;
        out += r; n -= (size_t)r;
    }
    return 0;
}
/* Reproducible workload messages, never a key-generation RNG. */
static void init_messages(void) {
    uint64_t x = UINT64_C(0x7a14e5a197b2c031);
    for (unsigned i = 0; i < POOL; i++) for (unsigned j = 0; j < 64; j++) {
        x ^= x << 13; x ^= x >> 7; x ^= x << 17;
        messages[i][j] = (uint8_t)(x >> 32);
    }
}
static uint64_t now_ns(void) {
    struct timespec t;
    need(clock_gettime(CLOCK_MONOTONIC_RAW, &t) == 0, "clock_gettime");
    return (uint64_t)t.tv_sec * UINT64_C(1000000000) + (uint64_t)t.tv_nsec;
}
static void backend_init(void);
static void backend_keygen(void);
static void backend_encaps(unsigned i);
static void backend_decaps(unsigned i);
static void backend_check(void);

static int bench_main(int argc, char **argv, const char *scheme,
                      size_t pk_size, size_t ct_size, size_t seed_size) {
    init_messages(); backend_init(); backend_check();
    if (argc == 2 && strcmp(argv[1], "--check") == 0) {
        printf("{\"scheme\":\"%s\",\"status\":\"passed\",\"keys\":%u,"
               "\"roundtrips\":%u,\"pk_bytes\":%zu,\"ct_bytes\":%zu,\"seed_bytes\":%zu}\n",
               scheme, KEYS, POOL, pk_size, ct_size, seed_size);
        return 0;
    }
    cntru_cycle_init();cntru_single_task();
    unsigned kg_count = argc > 1 ? (unsigned)strtoul(argv[1], NULL, 10) : 32;
    unsigned kem_count = argc > 2 ? (unsigned)strtoul(argv[2], NULL, 10) : 2048;
    unsigned rotation = argc > 3 ? (unsigned)strtoul(argv[3], NULL, 10) % 3 : 0;
    unsigned pool_offset = argc > 4 ? (unsigned)strtoul(argv[4], NULL, 10) % POOL : 0;
    need(kg_count > 0 && kem_count > 0, "positive benchmark counts");
    /* Warm the exact same complete wire-facing operations for every target. */
    for (unsigned i = 0; i < 8; i++) backend_keygen();
    for (unsigned i = 0; i < 32; i++) { backend_encaps((pool_offset+i) % POOL); backend_decaps((pool_offset+i) % POOL); }
    /* Empty read pairs expose measurement overhead; never subtract it. */
    uint64_t read_overhead[31];
    for(unsigned i=0;i<31;i++) {
        cntru_cycle_reading a=cntru_read_cycles(),b=cntru_read_cycles();
        need(b.value>=a.value && b.enabled>=a.enabled && b.running>=a.running,
             "monotonic PMU overhead readings");
        need(b.enabled-a.enabled==b.running-a.running && b.running>a.running,
             "PMU overhead counter must run without multiplexing");
        read_overhead[i]=b.value-a.value;
    }
    printf("{\"scheme\":\"%s\",\"clock\":\"PERF_COUNT_HW_CPU_CYCLES\",\"counter_owner_pid\":%ld,"
           "\"pk_bytes\":%zu,\"ct_bytes\":%zu,\"seed_bytes\":%zu,\"pool\":%u,\"keys\":%u,"
           "\"correctness_roundtrips\":%u,\"pool_offset\":%u,\"counter_read_overhead_cycles\":[",
           scheme, (long)getpid(), pk_size, ct_size, seed_size, POOL, KEYS, POOL, pool_offset);
    for(unsigned i=0;i<31;i++)printf("%s%llu",i?",":"",(unsigned long long)read_overhead[i]);
    fputs("],\"batches\":[",stdout);
    const char *names[] = {"keygen", "encaps", "decaps"};
    for (unsigned step = 0; step < 3; step++) {
        unsigned op = (step + rotation) % 3;
        unsigned n = op == 0 ? kg_count : kem_count;
        cntru_single_task();
        struct rusage before, after;
        int first_cpu = sched_getcpu();
        uint64_t bytes_before = rng_bytes, calls_before = rng_calls;
        need(getrusage(RUSAGE_SELF, &before) == 0, "getrusage start");
        uint64_t start = now_ns();
        cntru_cycle_reading cycle_start=cntru_read_cycles();
        for (unsigned i = 0; i < n; i++) {
            if (op == 0) backend_keygen();
            else if (op == 1) backend_encaps((pool_offset+i) % POOL);
            else backend_decaps((pool_offset+i) % POOL);
        }
        cntru_cycle_reading cycle_end=cntru_read_cycles();
        uint64_t elapsed = now_ns() - start;
        need(cycle_end.value>=cycle_start.value && cycle_end.enabled>=cycle_start.enabled
             && cycle_end.running>=cycle_start.running,"monotonic raw PMU readings");
        uint64_t cycles=cycle_end.value-cycle_start.value;
        need(getrusage(RUSAGE_SELF, &after) == 0, "getrusage end");
        int last_cpu = sched_getcpu();
        cntru_single_task();
        printf("%s{\"operation\":\"%s\",\"count\":%u,\"elapsed_ns\":%llu,"
               "\"ns_per_operation\":%.9f,\"cpu_start\":%d,\"cpu_end\":%d,"
               "\"voluntary_context_switches\":%ld,\"involuntary_context_switches\":%ld,"
               "\"minor_faults\":%ld,\"major_faults\":%ld,\"rng_calls\":%llu,\"rng_bytes\":%llu,\"elapsed_cycles\":%llu,\"cycles_per_operation\":%.9f,"
               "\"counter_start\":[%llu,%llu,%llu],\"counter_end\":[%llu,%llu,%llu]}",
               step ? "," : "", names[op], n, (unsigned long long)elapsed,
               (double)elapsed/n, first_cpu, last_cpu,
               after.ru_nvcsw-before.ru_nvcsw, after.ru_nivcsw-before.ru_nivcsw,
               after.ru_minflt-before.ru_minflt, after.ru_majflt-before.ru_majflt,
               (unsigned long long)(rng_calls-calls_before),
               (unsigned long long)(rng_bytes-bytes_before),
               (unsigned long long)cycles,(double)cycles/n,
               (unsigned long long)cycle_start.value,(unsigned long long)cycle_start.enabled,
               (unsigned long long)cycle_start.running,(unsigned long long)cycle_end.value,
               (unsigned long long)cycle_end.enabled,(unsigned long long)cycle_end.running);
        fflush(stdout);
    }
    close(cntru_cycle_fd);cntru_cycle_fd=-1;
    backend_check();
    printf("],\"checksum\":%llu}\n", (unsigned long long)checksum);
    return 0;
}
#endif
