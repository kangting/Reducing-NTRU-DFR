#ifndef CNTRU_CT_LOOKUP_H
#define CNTRU_CT_LOOKUP_H
#include <stddef.h>
#include <stdint.h>
#if defined(__AVX2__)
#include <immintrin.h>
#endif
/* cursor < length <= 256, length a public multiple of32. Every suffix byte is
 * read on every call. Vector addresses and loop bounds are independent of the
 * cursor. This preserves the compact-prefix tape map of both ring sizes. */
static inline uint32_t cntru_oblivious_byte(const uint8_t *suffix,
                                           unsigned length,unsigned cursor) {
#if defined(__AVX2__)
    const __m256i ramp=_mm256_setr_epi8(0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,
                                      16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31);
    __m256i result=_mm256_setzero_si256(),target=_mm256_set1_epi8((char)cursor);
    for(unsigned k=0;k<length;k+=32) {
        /* __m256i_u has byte alignment; volatile prevents a secret-address
         * lookup replacement and forces all public-address vector loads. */
        __m256i bytes=*(const volatile __m256i_u *)(const void *)(suffix+k);
        __m256i indices=_mm256_add_epi8(ramp,_mm256_set1_epi8((char)k));
        result=_mm256_or_si256(result,_mm256_and_si256(bytes,_mm256_cmpeq_epi8(indices,target)));
    }
    __m256i sums=_mm256_sad_epu8(result,_mm256_setzero_si256());
    __m128i s=_mm_add_epi64(_mm256_castsi256_si128(sums),_mm256_extracti128_si256(sums,1));
    s=_mm_add_epi64(s,_mm_srli_si128(s,8));
    return (uint32_t)_mm_cvtsi128_si64(s);
#else
    uint32_t result=0;
    for(unsigned k=0;k<length;k++) {
        uint32_t x=k^cursor;
        uint32_t equal=1U^((x|(0U-x))>>31);
        __asm__ __volatile__("" : "+r"(equal));
        result|=((const volatile uint8_t*)suffix)[k]&(0U-equal);
    }
    return result;
#endif
}
#endif
