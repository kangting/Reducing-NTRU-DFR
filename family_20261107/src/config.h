#ifndef CNTRU_FAMILY_CONFIG_H
#define CNTRU_FAMILY_CONFIG_H
#include "profile_ids.h"
#ifndef CNTRU_FAMILY_PROFILE
#error "Compile with a profile selector from profile_ids.h"
#endif
#include "profiles.h"
#define CNTRU_HALF (CNTRU_N/2)
#define CNTRU_BLOCKS (CNTRU_N/4)
/* The inverse always lives over n/2 bits, including D with u=n/4. */
#define CNTRU_U_WORDS (CNTRU_HALF/64)
#define CNTRU_KEY_BYTES 32
#define CNTRU_SAMPLE_BYTES (CNTRU_BLOCKS*CNTRU_WORD_BYTES)
#define CNTRU_RHO_BYTES (CNTRU_SAMPLE_BYTES+CNTRU_BLOCKS)
#define CNTRU_COINS_BYTES (CNTRU_U_BYTES+CNTRU_RHO_BYTES)
#define CNTRU_F_POOL_BYTES (CNTRU_F_CANDIDATES*CNTRU_SAMPLE_BYTES)
#define CNTRU_G_POOL_BYTES (2*CNTRU_SAMPLE_BYTES)
#define CNTRU_REDUCTION_BIAS (CNTRU_Q*524288)
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
#define cntru_sk CNTRU_NAMESPACE(sk)
#define cntru_rng CNTRU_NAMESPACE(rng)
#endif
