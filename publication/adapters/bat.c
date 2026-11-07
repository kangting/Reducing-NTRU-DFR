#include "driver.h"
#include "bat.h"
/* Benchmark-only entropy hook; author cryptographic sources are unchanged. */
int __wrap_bat_get_seed(void *out, size_t n) { return os_random(NULL, out, n) == 0; }
static bat_257_512_private_key sk[KEYS], scratch_sk;
static bat_257_512_public_key scratch_pk;
static bat_257_512_ciphertext scratch_ct;
static uint8_t pk[KEYS][521], ct[POOL][473], shared[POOL][32];
static uint8_t scratch_pkb[521], scratch_ctb[473], scratch_key[32];
static uint8_t tmp[BAT_257_512_TMP_KEYGEN];
static void backend_init(void) {
    for (unsigned j = 0; j < KEYS; j++) {
        need(bat_257_512_keygen(&sk[j], tmp, sizeof tmp) == 0, "keygen setup");
        bat_257_512_get_public_key(&scratch_pk, &sk[j]);
        need(bat_257_512_encode_public_key(pk[j], sizeof pk[j], &scratch_pk) == sizeof pk[j], "pk setup");
    }
    for (unsigned j = 0; j < POOL; j++) {
        need(bat_257_512_decode_public_key(&scratch_pk, pk[j % KEYS], sizeof pk[0]) == sizeof pk[0], "pk decode setup");
        need(bat_257_512_encapsulate_explicit_seed(shared[j], 32, &scratch_ct,
            &scratch_pk, messages[j], tmp, sizeof tmp) == 0, "encaps setup");
        need(bat_257_512_encode_ciphertext(ct[j], sizeof ct[j], &scratch_ct) == sizeof ct[j], "ct setup");
    }
}
static void backend_keygen(void) {
    need(bat_257_512_keygen(&scratch_sk, tmp, sizeof tmp) == 0, "keygen");
    bat_257_512_get_public_key(&scratch_pk, &scratch_sk);
    need(bat_257_512_encode_public_key(scratch_pkb, sizeof scratch_pkb, &scratch_pk) == sizeof scratch_pkb, "pk encode");
    observe(scratch_pkb, sizeof scratch_pkb); observe(&scratch_sk, sizeof scratch_sk);
}
static void backend_encaps(unsigned i) {
    need(bat_257_512_decode_public_key(&scratch_pk, pk[i % KEYS], sizeof pk[0]) == sizeof pk[0], "pk decode");
    need(bat_257_512_encapsulate_explicit_seed(scratch_key, 32, &scratch_ct,
        &scratch_pk, messages[i], tmp, sizeof tmp) == 0, "encaps");
    need(bat_257_512_encode_ciphertext(scratch_ctb, sizeof scratch_ctb, &scratch_ct) == sizeof scratch_ctb, "ct encode");
    observe(scratch_ctb, sizeof scratch_ctb); observe(scratch_key, sizeof scratch_key);
}
static void backend_decaps(unsigned i) {
    need(bat_257_512_decode_ciphertext(&scratch_ct, ct[i], sizeof ct[i]) == sizeof ct[i], "ct decode");
    need(bat_257_512_decapsulate(scratch_key, 32, &scratch_ct,
        &sk[i % KEYS], tmp, sizeof tmp) == 0, "decaps");
    observe(scratch_key, sizeof scratch_key);
}
static void backend_check(void) {
    for (unsigned i = 0; i < POOL; i++) {
        backend_decaps(i); need(memcmp(scratch_key, shared[i], 32) == 0, "shared key");
        backend_encaps(i); need(memcmp(scratch_ctb, ct[i], sizeof scratch_ctb) == 0, "deterministic ciphertext");
        need(memcmp(scratch_key, shared[i], 32) == 0, "deterministic shared key");
    }
}
int main(int argc, char **argv) { return bench_main(argc, argv, "BAT-512", 521, 473); }
