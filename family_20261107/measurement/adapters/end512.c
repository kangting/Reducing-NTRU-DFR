#include "driver.h"
#include "param.h"
#include "keygen.h"
#include "kem.h"
typedef struct {
    _Alignas(32) int8_t h[PKLEN];
    _Alignas(32) int8_t f[DIM_N];
    _Alignas(32) int8_t g[DIM_N];
    _Alignas(32) int8_t F[DIM_N];
    _Alignas(32) int8_t G[DIM_N];
    _Alignas(32) int8_t k[DIM_N];
    _Alignas(32) int16_t w[DIM_N];
} end_key;
static end_key sk[KEYS], scratch_sk;
static int8_t ct[POOL][CIPHLEN], shared[POOL][32], scratch_ct[CIPHLEN], scratch_key[32];
_Alignas(32) static uint32_t tmp[(22 * DIM_N + 32) / 4];
static const uint8_t *active_message;
/* END lacks an explicit-message encaps API. Supply the public randombytes
 * dependency at link time; cryptographic source files are unmodified.
 * Key generation still receives OS randomness. */
void randombytes(uint8_t *out, size_t n) {
    if (active_message) {
        need(n == 32, "END seeded encaps randomness size");
        memcpy(out, active_message, n);
    } else need(os_random(NULL, out, n) == 0, "OS random");
}
static void make_key(end_key *s) {
    active_message = NULL;
    END_keygen(s->h, s->f, s->g, s->F, s->G, s->w, s->k, tmp, 22 * DIM_N);
}
static void backend_init(void) {
    for (unsigned j = 0; j < KEYS; j++) make_key(&sk[j]);
    for (unsigned j = 0; j < POOL; j++) {
        active_message = messages[j];
        END_cca_encrypt(sk[j % KEYS].h, ct[j], shared[j]);
    }
    active_message = NULL;
}
static void backend_keygen(void) {
    make_key(&scratch_sk);
    observe(scratch_sk.h, sizeof scratch_sk.h); observe(&scratch_sk, sizeof scratch_sk);
}
static void backend_encaps(unsigned i) {
    active_message = messages[i];
    END_cca_encrypt(sk[i % KEYS].h, scratch_ct, scratch_key);
    active_message = NULL;
    observe(scratch_ct, sizeof scratch_ct); observe(scratch_key, sizeof scratch_key);
}
static void backend_decaps(unsigned i) {
    end_key *s = &sk[i % KEYS];
    END_cca_decrypt(s->h, ct[i], scratch_key, s->f, s->g, s->F, s->G, s->k, s->w);
    observe(scratch_key, sizeof scratch_key);
}
static void backend_check(void) {
    for (unsigned i = 0; i < POOL; i++) {
        backend_decaps(i); need(memcmp(scratch_key, shared[i], 32) == 0, "shared key");
        backend_encaps(i); need(memcmp(scratch_ct, ct[i], sizeof scratch_ct) == 0, "deterministic ciphertext");
        need(memcmp(scratch_key, shared[i], 32) == 0, "deterministic shared key");
    }
}
int main(int argc, char **argv) { return bench_main(argc, argv, "END-512", PKLEN, CIPHLEN, 32); }
