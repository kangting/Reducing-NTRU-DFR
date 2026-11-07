#ifndef CNTRU_LEVELS_CONFIG_H
#define CNTRU_LEVELS_CONFIG_H
#include <stdint.h>
#ifndef CNTRU_Q
#error "Compile with -DCNTRU_Q=307,331,or373"
#endif
#define CNTRU_N 1024
#define CNTRU_HALF 512
#define CNTRU_BLOCKS 256
#define CNTRU_U_BYTES 64
#define CNTRU_U_WORDS 8
#define CNTRU_KEY_BYTES 32
#define CNTRU_MESSAGE_BYTES 32
#define CNTRU_SAMPLE_BYTES 512
#define CNTRU_RHO_BYTES 768
#define CNTRU_COINS_BYTES 832
#define CNTRU_F_POOL_BYTES 131072
#define CNTRU_G_POOL_BYTES 1024
#define CNTRU_CODEC_LIMBS 288
#define CNTRU_CODEC_CHUNKS 342
#define CNTRU_REDUCTION_BIAS (CNTRU_Q*524288)
#if CNTRU_Q == 307
#define CNTRU_NAMESPACE(name) cntru1024q307_##name
#elif CNTRU_Q == 331
#define CNTRU_NAMESPACE(name) cntru1024q331_##name
#elif CNTRU_Q == 373
#define CNTRU_NAMESPACE(name) cntru1024q373_##name
#else
#error "Unsupported1024-degree profile"
#endif
#include "profiles.h"
#define cntru_sk CNTRU_NAMESPACE(sk)
#define cntru_rng CNTRU_NAMESPACE(rng)
#define cntru_keygen CNTRU_NAMESPACE(keygen)
#define cntru_base_encrypt CNTRU_NAMESPACE(base_encrypt)
#define cntru_base_decrypt CNTRU_NAMESPACE(base_decrypt)
#define cntru_encrypt CNTRU_NAMESPACE(encrypt)
#define cntru_decrypt CNTRU_NAMESPACE(decrypt)
#define cntru_deterministic_encrypt CNTRU_NAMESPACE(deterministic_encrypt)
#define cntru_encaps CNTRU_NAMESPACE(encaps)
#define cntru_decaps CNTRU_NAMESPACE(decaps)
#define cntru_randombytes CNTRU_NAMESPACE(randombytes)
#define cntru_shake256 CNTRU_NAMESPACE(shake256)
#define cntru_pack CNTRU_NAMESPACE(pack)
#define cntru_unpack CNTRU_NAMESPACE(unpack)
#define cntru_poly_mul CNTRU_NAMESPACE(poly_mul)
#define cntru_poly_inv CNTRU_NAMESPACE(poly_inv)
#define cntru_sample_poly CNTRU_NAMESPACE(sample_poly)
#define cntru_sample_rm CNTRU_NAMESPACE(sample_rm)
#define cntru_ct_poly_mul_n CNTRU_NAMESPACE(ct_poly_mul_n)
#define cntru_ct_poly_mul_avx2 CNTRU_NAMESPACE(ct_poly_mul_avx2)
#define cntru_ct_poly_inverse_n CNTRU_NAMESPACE(ct_poly_inverse_n)
#define cntru_ct_poly_unit_n CNTRU_NAMESPACE(ct_poly_unit_n)
#endif
