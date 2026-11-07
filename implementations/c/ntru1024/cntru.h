#ifndef CNTRU_LEVELS_H
#define CNTRU_LEVELS_H
#include <stddef.h>
#include <stdint.h>
#include "config.h"
typedef int (*cntru_rng)(void *,uint8_t *,size_t);
typedef struct {
    int16_t f[CNTRU_N];
    uint64_t fp_inverse[CNTRU_U_WORDS];
    /* Expanded key ABI v2: parsed public polynomial, no secret-key wire format. */
    int16_t h[CNTRU_N];
    uint8_t public_key[CNTRU_PK_BYTES];
    uint8_t rejection_seed[CNTRU_KEY_BYTES];
} cntru_sk;
/* Fixed-pool keygen requests131072,1024,32 bytes. Pool/RNG failure returns-1
 * and zeroes both complete outputs. Default RNG uses Linux getrandom. */
int cntru_keygen(uint8_t pk[CNTRU_PK_BYTES],cntru_sk *,cntru_rng,void *);
/* Internal residues are64 bytes; external messages/shared keys remain32.
 * Randomized base encryption consumes a fixed768-byte rho tape. */
int cntru_base_encrypt(uint8_t ct[CNTRU_CORE_BYTES],const uint8_t pk[CNTRU_PK_BYTES],const uint8_t u[CNTRU_U_BYTES],cntru_rng,void *);
/* Noncanonical cores return-1 and zero all64 output bytes. */
int cntru_base_decrypt(uint8_t u[CNTRU_U_BYTES],const cntru_sk *,const uint8_t ct[CNTRU_CORE_BYTES]);
int cntru_encrypt(uint8_t ct[CNTRU_CT_BYTES],const uint8_t pk[CNTRU_PK_BYTES],const uint8_t message[32],cntru_rng,void *);
int cntru_decrypt(uint8_t message[32],const cntru_sk *,const uint8_t *,size_t);
int cntru_deterministic_encrypt(uint8_t ct[CNTRU_CT_BYTES],const uint8_t pk[CNTRU_PK_BYTES],const uint8_t message[32]);
int cntru_encaps(uint8_t ct[CNTRU_CT_BYTES],uint8_t key[32],const uint8_t pk[CNTRU_PK_BYTES],cntru_rng,void *);
/* Implicit rejection binds every received byte, including malformed lengths. */
int cntru_decaps(uint8_t key[32],const cntru_sk *,const uint8_t *,size_t);
int cntru_randombytes(void *,uint8_t *,size_t);
void cntru_shake256(uint8_t *,size_t,const uint8_t *,size_t);
/* Polynomial inputs lie in[-(q-1),q-1]. Output may alias either input. */
int cntru_pack(uint8_t [CNTRU_PK_BYTES],const int16_t [CNTRU_N]);
int cntru_unpack(int16_t [CNTRU_N],const uint8_t [CNTRU_PK_BYTES]);
void cntru_poly_mul(int16_t [CNTRU_N],const int16_t [CNTRU_N],const int16_t [CNTRU_N]);
int cntru_poly_inv(int16_t [CNTRU_N],const int16_t [CNTRU_N]);
int cntru_sample_poly(int16_t [CNTRU_N],unsigned,cntru_rng,void *);
int cntru_sample_rm(int16_t [CNTRU_N],int16_t [CNTRU_N],const uint8_t [CNTRU_U_BYTES],cntru_rng,void *);
#endif
