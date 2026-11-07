#ifndef CNTRU_H
#define CNTRU_H
#include <stddef.h>
#include <stdint.h>

#define CNTRU_N 512
#define CNTRU_Q 211
#define CNTRU_PK_BYTES 495
#define CNTRU_CORE_BYTES 495
#define CNTRU_CT_BYTES 527
#define CNTRU_KEY_BYTES 32

/* An RNG returns 0 after filling exactly len bytes; nonzero means failure. */
typedef int (*cntru_rng)(void *ctx, uint8_t *out, size_t len);
typedef struct {
    int16_t f[CNTRU_N];
    uint64_t fp_inverse[4];
    /* Expanded key ABI v2: parsed public polynomial, no secret-key wire format. */
    int16_t h[CNTRU_N];
    uint8_t public_key[CNTRU_PK_BYTES];
    uint8_t rejection_seed[CNTRU_KEY_BYTES];
} cntru_sk;

/* All functions return 0 on success, -1 on error. The fixed-size pointers
 * below must reference buffers of the declared size. Decapsulation accepts
 * every ciphertext length, including zero, and implicitly rejects invalid
 * ciphertexts with the reference H(ctx, received_bytes, rejection_seed). */
/* Keygen uses a fixed pool:256 f candidates and2 g candidates. RNG calls
 * request65536,512,32 bytes respectively; pool failure returns-1 with wiped
 * outputs. The output distribution conditioned on success is unchanged. */
int cntru_keygen(uint8_t pk[495], cntru_sk *sk, cntru_rng rng, void *ctx);
/* Base encryption/sample_rm consume a fixed384-byte tape, including unused
 * conditional lift bytes. This changes RNG scheduling, not deterministic KEM
 * ciphertexts. All polynomial helpers have fixed schedules at public n=512. */
int cntru_base_encrypt(uint8_t ct[495], const uint8_t pk[495],
    const uint8_t u[32], cntru_rng rng, void *ctx);
/* Noncanonical 495-byte ciphertexts return -1 and zero every byte of u. */
int cntru_base_decrypt(uint8_t u[32], const cntru_sk *sk, const uint8_t ct[495]);
int cntru_encrypt(uint8_t ct[527], const uint8_t pk[495], const uint8_t message[32],
    cntru_rng rng, void *ctx);
int cntru_decrypt(uint8_t message[32], const cntru_sk *sk, const uint8_t *ct,
    size_t ct_len);
int cntru_deterministic_encrypt(uint8_t ct[527], const uint8_t pk[495],
    const uint8_t message[32]);
int cntru_encaps(uint8_t ct[527], uint8_t key[32], const uint8_t pk[495],
    cntru_rng rng, void *ctx);
int cntru_decaps(uint8_t key[32], const cntru_sk *sk, const uint8_t *ct,
    size_t ct_len);
int cntru_randombytes(void *ctx, uint8_t *out, size_t len);
void cntru_shake256(uint8_t *out, size_t out_len, const uint8_t *in, size_t in_len);

/* Oracle-test arithmetic helpers. Poly inputs are coefficients in [-210,210].
 * pack() requires coefficients in [0,210]. Aliased poly output is supported. */
int cntru_pack(uint8_t encoded[495], const int16_t coefficients[512]);
int cntru_unpack(int16_t coefficients[512], const uint8_t encoded[495]);
void cntru_poly_mul(int16_t out[512], const int16_t a[512], const int16_t b[512]);
int cntru_poly_inv(int16_t out[512], const int16_t in[512]);
int cntru_sample_poly(int16_t out[512], unsigned which, cntru_rng rng, void *ctx);
int cntru_sample_rm(int16_t r[512], int16_t m[512], const uint8_t u[32],
    cntru_rng rng, void *ctx);

#endif
