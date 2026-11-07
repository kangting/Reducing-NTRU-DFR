#ifndef CNTRU_LEVELS_CT_UTIL_H
#define CNTRU_LEVELS_CT_UTIL_H
#include <stddef.h>
#include <stdint.h>
#include "config.h"

/* These source-level idioms still require compiler/binary verification. */
static inline uint32_t ct_nonzero_u32(uint32_t x) {
    return (x | (0U-x)) >> 31;
}
static inline uint32_t ct_equal_u32(uint32_t x, uint32_t y) {
    return 1U ^ ct_nonzero_u32(x^y);
}
static inline uint32_t ct_less_u32(uint32_t x, uint32_t y) {
    return (uint32_t)(((uint64_t)x-(uint64_t)y)>>63);
}
static inline uint32_t ct_barrier_u32(uint32_t x) {
#if defined(__GNUC__) || defined(__clang__)
    __asm__ volatile("" : "+r"(x));
#else
    volatile uint32_t copy=x; x=copy;
#endif
    return x;
}
static inline uint64_t ct_barrier_u64(uint64_t x) {
#if defined(__GNUC__) || defined(__clang__)
    __asm__ volatile("" : "+r"(x));
#else
    volatile uint64_t copy=x; x=copy;
#endif
    return x;
}
static inline uint32_t ct_mask_u32(uint32_t bit) {
    return ct_barrier_u32(0U-bit);
}
static inline uint64_t ct_mulhi_u64(uint64_t a,uint64_t b) {
#if defined(__SIZEOF_INT128__)
    __extension__ typedef unsigned __int128 cntru_u128;
    return (uint64_t)(((cntru_u128)a*b)>>64);
#else
    uint64_t a0=(uint32_t)a,a1=a>>32,b0=(uint32_t)b,b1=b>>32;
    uint64_t t=a0*b0,k=t>>32;
    t=a1*b0+k;
    uint64_t w1=(uint32_t)t,w2=t>>32;
    t=a0*b1+w1;
    return a1*b1+w2+(t>>32);
#endif
}
static inline void cntru_secure_wipe(void *v,size_t n) {
    volatile uint8_t *p=(volatile uint8_t*)v;
    while(n--) *p++=0;
}

/* Reciprocal reduction for the documented intermediate bounds. The added
 * q*2^19 is a multiple of q and exceeds every centered1024-degree bound. */
static inline int16_t ct_mod_q(int32_t x) {
    uint32_t u=(uint32_t)(x+CNTRU_REDUCTION_BIAS);
    uint32_t quotient=(uint32_t)(((uint64_t)u*CNTRU_Q_RECIPROCAL)>>32);
    uint32_t product=quotient*CNTRU_Q;
    uint32_t borrow=ct_less_u32(u,product);
    return (int16_t)(u-product+borrow*CNTRU_Q);
}
/* x in[-(q-1),q-1]. Centering preserves its residue modulo q. */
static inline int16_t ct_center_q(int16_t x) {
    uint32_t u=(uint32_t)(int32_t)x;
    u+=CNTRU_Q&(0U-(u>>31));
    return (int16_t)((int32_t)u-(int32_t)(CNTRU_Q*ct_less_u32(CNTRU_Q/2,u)));
}
#endif
