#ifndef CNTRU_FAMILY_H
#define CNTRU_FAMILY_H
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
    uint8_t rejection_seed[CNTRU_MESSAGE_BYTES];
} cntru_sk;
/* Generated fixed-pool keygen requests F_POOL_BYTES,G_POOL_BYTES,MESSAGE_BYTES.
 * Each exact pool exhaustion bound is <=2^-256; source/pool failures wipe both
 * complete outputs. Public profile selection is mandatory at compile time. */
int cntru_keygen(uint8_t pk[CNTRU_PK_BYTES],cntru_sk *,cntru_rng,void *);
/* Sizes follow config.h: S internal residue n/2 bits; D n/4 bits. External
 * messages are128/256 bits; shared-key output256 bits is a length, not a
 * security claim. New fixed public block slots define a versioned byte map. */
int cntru_base_encrypt(uint8_t ct[CNTRU_CORE_BYTES],const uint8_t pk[CNTRU_PK_BYTES],const uint8_t u[CNTRU_U_BYTES],cntru_rng,void *);
/* Noncanonical cores or D correction/repeated-half faults return-1 and zero u. */
int cntru_base_decrypt(uint8_t u[CNTRU_U_BYTES],const cntru_sk *,const uint8_t ct[CNTRU_CORE_BYTES]);
int cntru_encrypt(uint8_t ct[CNTRU_CT_BYTES],const uint8_t pk[CNTRU_PK_BYTES],const uint8_t message[CNTRU_MESSAGE_BYTES],cntru_rng,void *);
int cntru_decrypt(uint8_t message[CNTRU_MESSAGE_BYTES],const cntru_sk *,const uint8_t *,size_t);
int cntru_deterministic_encrypt(uint8_t ct[CNTRU_CT_BYTES],const uint8_t pk[CNTRU_PK_BYTES],const uint8_t message[CNTRU_MESSAGE_BYTES]);
int cntru_encaps(uint8_t ct[CNTRU_CT_BYTES],uint8_t key[CNTRU_KEY_BYTES],const uint8_t pk[CNTRU_PK_BYTES],cntru_rng,void *);
/* Implicit rejection binds every received byte, including malformed lengths. */
int cntru_decaps(uint8_t key[CNTRU_KEY_BYTES],const cntru_sk *,const uint8_t *,size_t);
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
