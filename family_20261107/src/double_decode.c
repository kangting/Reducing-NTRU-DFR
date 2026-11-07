#include "double_decode.h"
#include "ct_util.h"

_Static_assert(CNTRU_N==512 || CNTRU_N==1024,"D decoder supports N512/N1024");
_Static_assert(CNTRU_BLOCKS*4==CNTRU_N,"D quartet layout");
_Static_assert(CNTRU_HALF*2==CNTRU_N,"D residue dimension");
_Static_assert(CNTRU_U_WORDS*64==CNTRU_HALF,"D residue word count");

/* Unsigned conversion and arithmetic avoid negating INT16_MIN in its
 * original type. For a sign-extended int16 value, magnitude is in[0,32768]. */
static inline uint32_t magnitude_i16(int16_t value) {
    uint32_t bits=(uint32_t)(int32_t)value;
    uint32_t negative=bits>>31;
    return (bits^ct_mask_u32(negative))+negative;
}

uint32_t cntru_double_residue(uint64_t out[CNTRU_U_WORDS],
                              const int16_t centered[CNTRU_N]) {
    uint32_t syndrome_count=0;
    for(unsigned i=0;i<CNTRU_BLOCKS;i++) {
        uint32_t syndrome=0;
        for(unsigned k=0;k<4;k++)
            syndrome^=(uint32_t)(uint16_t)centered[i+k*CNTRU_BLOCKS]&1U;
        syndrome_count+=syndrome&1U;
    }

    /* Count lies in[0,N/4]. Strictly one enables correction; zero enables
     * none, and failure cases keep their original residue for the caller's
     * final masked rejection path. No syndrome position becomes an address. */
    uint32_t exactly_one=ct_equal_u32(syndrome_count,1U);
    for(unsigned word=0;word<CNTRU_U_WORDS;word++)out[word]=0;
    for(unsigned i=0;i<CNTRU_BLOCKS;i++) {
        uint32_t parity[4],syndrome=0;
        uint32_t maximum=0,selected=0;
        for(unsigned k=0;k<4;k++) {
            int16_t value=centered[i+k*CNTRU_BLOCKS];
            parity[k]=(uint32_t)(int32_t)value&1U;
            syndrome^=parity[k];
            uint32_t magnitude=magnitude_i16(value);
            /* Replace only for a STRICT improvement, preserving the first
             * index when multiple coefficients have equal magnitude. */
            uint32_t replace=ct_less_u32(maximum,magnitude);
            uint32_t mask=ct_mask_u32(replace);
            maximum^=(maximum^magnitude)&mask;
            selected^=(selected^k)&mask;
        }
        uint32_t active=exactly_one&syndrome;
        for(unsigned k=0;k<4;k++)
            parity[k]^=active&ct_equal_u32(selected,k);

        /* In characteristic2, x^(N/2)=-1=1; opposite quartet positions
         * fold together. These shifts and word indexes are public. */
        out[i>>6]|=(uint64_t)(parity[0]^parity[2])<<(i&63U);
        unsigned second=i+CNTRU_BLOCKS;
        out[second>>6]|=(uint64_t)(parity[1]^parity[3])<<(second&63U);
    }
    return ct_less_u32(syndrome_count,2U);
}
