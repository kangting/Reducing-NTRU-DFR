#ifndef CNTRU_COMMON_CT_RADIX_H
#define CNTRU_COMMON_CT_RADIX_H
#include <stddef.h>
#include <stdint.h>

/* Optional token prefix, e.g. -DCT_RADIX_PREFIX=cntru1024q373_common_. Apply
 * the identical definition to this source and every including translation
 * unit. Generated immutable plan names have internal linkage. */
#ifdef CT_RADIX_PREFIX
#define CT_RADIX_JOIN_(a,b) a##b
#define CT_RADIX_JOIN(a,b) CT_RADIX_JOIN_(a,b)
#define ct_radix_plan_init CT_RADIX_JOIN(CT_RADIX_PREFIX,plan_init)
#define ct_radix_pack CT_RADIX_JOIN(CT_RADIX_PREFIX,pack)
#define ct_radix_unpack CT_RADIX_JOIN(CT_RADIX_PREFIX,unpack)
#define ct_radix_divrem CT_RADIX_JOIN(CT_RADIX_PREFIX,divrem)
#endif

/* A plan is public, immutable while in use, and must come from plan_init or
 * ct_radix_generate.py. Initialization is outside the secret-processing API.
 * This implementation requires an unsigned 128-bit integer type. */
#define CT_RADIX_MAX_N 4096U
#define CT_RADIX_MAX_CHUNKS 1024U
#define CT_RADIX_MAX_LIMBS 960U
typedef struct {
    uint32_t n, q, encoded_bytes, limbs, digits, chunks, shift;
    uint64_t divisor, normalized_divisor, reciprocal, digit_reciprocal;
    uint16_t pack_limbs[CT_RADIX_MAX_CHUNKS];
    uint16_t unpack_limbs[CT_RADIX_MAX_CHUNKS];
} ct_radix_plan;

/* Public n in [1,4096], odd q in [3,32767]. Returns 0, or -1 and zeroes p.
 * Public initialization may use integer division and value-dependent loops. */
#ifndef CT_RADIX_STATIC_PLANS_ONLY
int ct_radix_plan_init(ct_radix_plan *p, uint32_t n, uint32_t q);
#endif

/* Exact little-endian encoding of sum a[i]*q^i in ceil(log_256(q^n)) bytes.
 * Pack accepts coefficients in [0,q); on error its complete output is zero.
 * Unpack rejects precisely integers >= q^n. Like the historical low-level
 * codec it still returns the n low base-q digits on noncanonical input.
 * Neither function branches, divides, or indexes memory on secret values.
 * Input and output buffers must not overlap. Both wipe their scratch space. */
int ct_radix_pack(uint8_t *encoded, const int16_t *a, const ct_radix_plan *p);
int ct_radix_unpack(int16_t *a, const uint8_t *encoded, const ct_radix_plan *p);

/* Exposed only for exhaustive/random arithmetic tests; d and reciprocal are
 * public and normalized (2^63 <= d < 2^64), hi < d. Returns quotient and rem.
 * reciprocal = floor(2^128/d)-2^64, requiring d not a power of two. */
uint64_t ct_radix_divrem(uint64_t *remainder, uint64_t hi, uint64_t lo,
                        uint64_t d, uint64_t reciprocal);
#endif
