#include "ct_ntt.h"
#ifdef CNTRU_AVX2_NTT
#if !defined(__AVX2__)
#error "CNTRU_AVX2_NTT requires AVX2 compiler flags and an AVX2-capable CPU"
#endif
#include "ct_util.h"
#include "ntt16_tables.h"
#include <immintrin.h>
#include <string.h>

typedef struct {
    uint16_t p,ninv,r2;
    const uint16_t *forward,*inverse,*inverse_lengths;
    const uint16_t (*forward_small)[16],(*inverse_small)[16];
} ntt16_modulus;
static const ntt16_modulus moduli[2]={
    {12289,12287,10952,ntt16_0_forward,ntt16_0_inverse,ntt16_0_inverse_lengths,ntt16_0_forward_small,ntt16_0_inverse_small},
    {15361,15359,974,ntt16_1_forward,ntt16_1_inverse,ntt16_1_inverse_lengths,ntt16_1_forward_small,ntt16_1_inverse_small}
};

static inline __m256i add16(__m256i a,__m256i b,__m256i p) {
    __m256i t=_mm256_sub_epi16(_mm256_add_epi16(a,b),p);
    return _mm256_add_epi16(t,_mm256_and_si256(_mm256_srai_epi16(t,15),p));
}
static inline __m256i sub16(__m256i a,__m256i b,__m256i p) {
    __m256i t=_mm256_sub_epi16(a,b);
    return _mm256_add_epi16(t,_mm256_and_si256(_mm256_srai_epi16(t,15),p));
}
static inline __m256i mont16(__m256i a,__m256i b,__m256i p,__m256i ninv) {
    /* All inputs are canonical in[0,p). Since p<2^14, the unreduced result
     * is below2p<2^15. Unsigned high halves are essential for the full-width
     * correction multiplier m. Low(T)+low(m*p) is65536 iff low(T)!=0. */
    __m256i low=_mm256_mullo_epi16(a,b);
    __m256i high=_mm256_mulhi_epu16(a,b);
    __m256i m=_mm256_mullo_epi16(low,ninv);
    __m256i correction=_mm256_mulhi_epu16(m,p);
    __m256i carry=_mm256_andnot_si256(_mm256_cmpeq_epi16(low,_mm256_setzero_si256()),_mm256_set1_epi16(1));
    __m256i t=_mm256_sub_epi16(_mm256_add_epi16(_mm256_add_epi16(high,correction),carry),p);
    return _mm256_add_epi16(t,_mm256_and_si256(_mm256_srai_epi16(t,15),p));
}
static inline __m256i neighbor(__m256i x,unsigned stage) {
    switch(stage) {
    case 0:return _mm256_shuffle_epi8(x,_mm256_setr_epi8(2,3,0,1,6,7,4,5,10,11,8,9,14,15,12,13,2,3,0,1,6,7,4,5,10,11,8,9,14,15,12,13));
    case 1:return _mm256_shuffle_epi32(x,0xb1);
    case 2:return _mm256_shuffle_epi32(x,0x4e);
    default:return _mm256_permute2x128_si256(x,x,1);
    }
}

/* Forward DIF and inverse DIT share bit-reversed frequency order. No
 * bit-reversal permutation, secret-indexed access, or data-dependent stage
 * reduction is required. The last/first four stages are16-lane butterflies. */
static void forward_ntt(uint16_t *a,unsigned length,const ntt16_modulus *mod) {
    __m256i p=_mm256_set1_epi16((short)mod->p),ninv=_mm256_set1_epi16((short)mod->ninv);
    for(unsigned size=length;size>=32;size>>=1) {
        unsigned half=size>>1;
        for(unsigned start=0;start<length;start+=size)for(unsigned j=0;j<half;j+=16) {
            __m256i u=_mm256_load_si256((const __m256i*)(a+start+j));
            __m256i v=_mm256_load_si256((const __m256i*)(a+start+j+half));
            __m256i w=_mm256_load_si256((const __m256i*)(mod->forward+half+j));
            _mm256_store_si256((__m256i*)(a+start+j),add16(u,v,p));
            _mm256_store_si256((__m256i*)(a+start+j+half),mont16(sub16(u,v,p),w,p,ninv));
        }
    }
    for(int stage=3;stage>=0;stage--) {
        __m256i w=_mm256_load_si256((const __m256i*)mod->forward_small[stage]);
        __m256i upper=_mm256_load_si256((const __m256i*)ntt16_upper_masks[stage]);
        for(unsigned j=0;j<length;j+=16) {
            __m256i x=_mm256_load_si256((const __m256i*)(a+j)),other=neighbor(x,(unsigned)stage);
            __m256i difference=sub16(other,x,p);
            if(stage)difference=mont16(difference,w,p,ninv); /* public stage */
            _mm256_store_si256((__m256i*)(a+j),_mm256_blendv_epi8(add16(x,other,p),difference,upper));
        }
    }
}
static void inverse_ntt(uint16_t *a,unsigned length,const ntt16_modulus *mod) {
    __m256i p=_mm256_set1_epi16((short)mod->p),ninv=_mm256_set1_epi16((short)mod->ninv);
    for(unsigned stage=0;stage<4;stage++) {
        __m256i w=_mm256_load_si256((const __m256i*)mod->inverse_small[stage]);
        __m256i upper=_mm256_load_si256((const __m256i*)ntt16_upper_masks[stage]);
        for(unsigned j=0;j<length;j+=16) {
            __m256i x=_mm256_load_si256((const __m256i*)(a+j));
            if(stage)x=mont16(x,w,p,ninv);
            __m256i other=neighbor(x,stage);
            _mm256_store_si256((__m256i*)(a+j),_mm256_blendv_epi8(add16(x,other,p),sub16(other,x,p),upper));
        }
    }
    for(unsigned size=32;size<=length;size<<=1) {
        unsigned half=size>>1;
        for(unsigned start=0;start<length;start+=size)for(unsigned j=0;j<half;j+=16) {
            __m256i u=_mm256_load_si256((const __m256i*)(a+start+j));
            __m256i v=_mm256_load_si256((const __m256i*)(a+start+j+half));
            __m256i w=_mm256_load_si256((const __m256i*)(mod->inverse+half+j));
            v=mont16(v,w,p,ninv);
            _mm256_store_si256((__m256i*)(a+start+j),add16(u,v,p));
            _mm256_store_si256((__m256i*)(a+start+j+half),sub16(u,v,p));
        }
    }
    unsigned logarithm=0;
    for(unsigned n=length;n>1;n>>=1)logarithm++;
    __m256i scale=_mm256_set1_epi16((short)mod->inverse_lengths[logarithm]);
    for(unsigned j=0;j<length;j+=16) {
        __m256i x=_mm256_load_si256((const __m256i*)(a+j));
        _mm256_store_si256((__m256i*)(a+j),mont16(x,scale,p,ninv));
    }
}
static inline __m256i reduce_q32(__m256i coefficient) {
    __m256i u=_mm256_add_epi32(coefficient,_mm256_set1_epi32(27656192));
    __m256i reciprocal=_mm256_set1_epi32(20355296);
    __m256i even=_mm256_srli_epi64(_mm256_mul_epu32(u,reciprocal),32);
    __m256i odd=_mm256_mul_epu32(_mm256_srli_epi64(u,32),reciprocal);
    __m256i quotient=_mm256_or_si256(even,_mm256_slli_epi64(_mm256_srli_epi64(odd,32),32));
    __m256i product=_mm256_mullo_epi32(quotient,_mm256_set1_epi32(211));
    __m256i borrow=_mm256_cmpgt_epi32(product,u); /* both below2^31 */
    return _mm256_add_epi32(_mm256_sub_epi32(u,product),_mm256_and_si256(borrow,_mm256_set1_epi32(211)));
}

void cntru_ct_poly_mul_avx2(int16_t *out,const int16_t *a,const int16_t *b,unsigned n) {
    _Alignas(32) uint16_t aa[1024],bb[1024],residues[2][512];
    for(unsigned modulus=0;modulus<2;modulus++) {
        const ntt16_modulus *mod=&moduli[modulus];
        __m256i p=_mm256_set1_epi16((short)mod->p),ninv=_mm256_set1_epi16((short)mod->ninv);
        __m256i r2=_mm256_set1_epi16((short)mod->r2);
        memset(aa,0,sizeof(aa));memset(bb,0,sizeof(bb));
        for(unsigned j=0;j<n;j+=16) {
            __m256i x=_mm256_loadu_si256((const __m256i*)(a+j));
            __m256i y=_mm256_loadu_si256((const __m256i*)(b+j));
            x=_mm256_add_epi16(x,_mm256_and_si256(_mm256_srai_epi16(x,15),p));
            y=_mm256_add_epi16(y,_mm256_and_si256(_mm256_srai_epi16(y,15),p));
            _mm256_store_si256((__m256i*)(aa+j),mont16(x,r2,p,ninv));
            _mm256_store_si256((__m256i*)(bb+j),mont16(y,r2,p,ninv));
        }
        forward_ntt(aa,2*n,mod);
        if(a==b)memcpy(bb,aa,2*n*sizeof(*bb));else forward_ntt(bb,2*n,mod);
        for(unsigned j=0;j<2*n;j+=16) {
            __m256i x=_mm256_load_si256((const __m256i*)(aa+j)),y=_mm256_load_si256((const __m256i*)(bb+j));
            _mm256_store_si256((__m256i*)(aa+j),mont16(x,y,p,ninv));
        }
        inverse_ntt(aa,2*n,mod);
        for(unsigned j=0;j<n;j+=16) {
            __m256i x=_mm256_load_si256((const __m256i*)(aa+j)),y=_mm256_load_si256((const __m256i*)(aa+j+n));
            __m256i normal=mont16(sub16(x,y,p),_mm256_set1_epi16(1),p,ninv);
            _mm256_store_si256((__m256i*)(residues[modulus]+j),normal);
        }
    }
    /* p1*p2=188771329 >2*512*210^2. Reconstruct r1+p1*t, with
     * t=(r2-r1)*p1^-1 modp2 and p1^-1=5. Centering is exact in the
     * documented coefficient range. The vector reciprocal then reduces211. */
    __m256i p2=_mm256_set1_epi16(15361),p2_ninv=_mm256_set1_epi16(15359);
    __m256i crt_inverse=_mm256_set1_epi16(5099); /* 5*2^16 mod15361 */
    __m256i crt_multipliers=_mm256_set1_epi32((12289<<16)|1);
    __m256i modulus=_mm256_set1_epi32(188771329),half=_mm256_set1_epi32(94385664);
    for(unsigned j=0;j<n;j+=16) {
        __m256i r1=_mm256_load_si256((const __m256i*)(residues[0]+j));
        __m256i r2=_mm256_load_si256((const __m256i*)(residues[1]+j));
        __m256i t=mont16(sub16(r2,r1,p2),crt_inverse,p2,p2_ninv);
        __m256i low=_mm256_madd_epi16(_mm256_unpacklo_epi16(r1,t),crt_multipliers);
        __m256i high=_mm256_madd_epi16(_mm256_unpackhi_epi16(r1,t),crt_multipliers);
        low=_mm256_sub_epi32(low,_mm256_and_si256(_mm256_cmpgt_epi32(low,half),modulus));
        high=_mm256_sub_epi32(high,_mm256_and_si256(_mm256_cmpgt_epi32(high,half),modulus));
        _mm256_storeu_si256((__m256i*)(out+j),_mm256_packus_epi32(reduce_q32(low),reduce_q32(high)));
    }
    cntru_secure_wipe(aa,sizeof(aa));cntru_secure_wipe(bb,sizeof(bb));cntru_secure_wipe(residues,sizeof(residues));
    _mm256_zeroall();
}
#endif
