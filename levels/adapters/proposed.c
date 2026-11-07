#include "driver.h"
#include "cntru.h"
static cntru_sk sk[KEYS], scratch_sk;
static uint8_t pk[KEYS][CNTRU_PK_BYTES], scratch_pk[CNTRU_PK_BYTES];
static uint8_t ct[POOL][CNTRU_CT_BYTES], shared[POOL][32], scratch_ct[CNTRU_CT_BYTES], scratch_key[32];
static int message_rng(void *ctx, uint8_t *out, size_t n) {
    if (n != 32) return -1;
    memcpy(out, ctx, n); return 0;
}
static void backend_init(void) {
    for (unsigned j = 0; j < KEYS; j++)
        need(cntru_keygen(pk[j], &sk[j], os_random, NULL) == 0, "keygen setup");
    for (unsigned j = 0; j < POOL; j++)
        need(cntru_encaps(ct[j], shared[j], pk[j % KEYS], message_rng,
            messages[j]) == 0, "encaps setup");
}
static void backend_keygen(void) {
    need(cntru_keygen(scratch_pk, &scratch_sk, os_random, NULL) == 0, "keygen");
    observe(scratch_pk, sizeof scratch_pk); observe(&scratch_sk, sizeof scratch_sk);
}
static void backend_encaps(unsigned i) {
    need(cntru_encaps(scratch_ct, scratch_key, pk[i % KEYS], message_rng,
        messages[i]) == 0, "encaps");
    observe(scratch_ct, sizeof scratch_ct); observe(scratch_key, sizeof scratch_key);
}
static void backend_decaps(unsigned i) {
    need(cntru_decaps(scratch_key, &sk[i % KEYS], ct[i], sizeof ct[i]) == 0, "decaps");
    observe(scratch_key, sizeof scratch_key);
}
static void backend_check(void) {
    for (unsigned i = 0; i < POOL; i++) {
        backend_decaps(i);
        need(memcmp(scratch_key, shared[i], 32) == 0, "shared key");
        backend_encaps(i);
        need(memcmp(scratch_ct, ct[i], sizeof scratch_ct) == 0, "deterministic ciphertext");
        need(memcmp(scratch_key, shared[i], 32) == 0, "deterministic shared key");
    }
}
int main(int argc, char **argv) { return bench_main(argc, argv, "Complementary-NTRU-n1024", CNTRU_PK_BYTES, CNTRU_CT_BYTES, 32); }
