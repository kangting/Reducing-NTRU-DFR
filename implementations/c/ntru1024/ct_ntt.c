#include "ct_ntt.h"
#include "ct_util.h"
#ifndef CNTRU_AVX2_NTT
#include "ntt_tables.h"
#endif
#include <string.h>

#ifndef CNTRU_AVX2_NTT
#define NTT_P UINT32_C(998244353)
#define NTT_R UINT32_C(301989884)
#define NTT_R2 UINT32_C(932051910)
#define NTT_NINV UINT32_C(998244351)

/* p<2^30. Every operand below is canonical in [0,p); the Montgomery
 * accumulator is below p^2+(2^32-1)p<2^63 and its quotient is below2p. */
static inline uint32_t montgomery(uint64_t x) {
    uint32_t k=(uint32_t)x*NTT_NINV;
    uint32_t t=(uint32_t)((x+(uint64_t)k*NTT_P)>>32);
    uint32_t reduced=t-NTT_P;
    return reduced+(NTT_P&(0U-(reduced>>31)));
}
static inline uint32_t multiply(uint32_t a,uint32_t b) {
    return montgomery((uint64_t)a*b);
}
static inline uint32_t add(uint32_t a,uint32_t b) {
    uint32_t t=a+b-NTT_P;
    return t+(NTT_P&(0U-(t>>31)));
}
static inline uint32_t subtract(uint32_t a,uint32_t b) {
    uint32_t t=a-b;
    return t+(NTT_P&(0U-(t>>31)));
}

/* All permutation branches and accesses depend only on the public length. */
static void transform(uint32_t *a,unsigned length,unsigned inverse) {
    for(unsigned i=1,j=0;i<length;i++) {
        unsigned bit=length>>1;
        for(;j&bit;bit>>=1)j^=bit;
        j^=bit;
        if(i<j){uint32_t t=a[i];a[i]=a[j];a[j]=t;}
    }
    const uint32_t *twiddles=inverse?ntt_inverse_twiddles:ntt_forward_twiddles;
    for(unsigned size=2;size<=length;size<<=1) {
        unsigned half=size>>1;
        for(unsigned start=0;start<length;start+=size)
            for(unsigned j=0;j<half;j++) {
                uint32_t u=a[start+j];
                uint32_t v=multiply(a[start+j+half],twiddles[half+j]);
                a[start+j]=add(u,v);
                a[start+j+half]=subtract(u,v);
            }
    }
    if(inverse) {
        unsigned logarithm=0;
        for(unsigned n=length;n>1;n>>=1)logarithm++;
        for(unsigned j=0;j<length;j++)a[j]=multiply(a[j],ntt_inverse_lengths[logarithm]);
    }
}
#endif

void cntru_ct_poly_mul_n(int16_t *out,const int16_t *a,const int16_t *b,unsigned n) {
    /* Public contract: n is a power of two <=1024; inputs lie in[-(q-1),q-1].
     * After centering,2*1024*186^2=70,852,608<p. Each coefficient therefore
     * has a unique centered lift after the auxiliary-prime convolution. */
    if(n<=16) {
        int32_t product[32]={0};
        for(unsigned i=0;i<n;i++)for(unsigned j=0;j<n;j++)product[i+j]+=(int32_t)a[i]*b[j];
        for(unsigned j=0;j<n;j++)out[j]=ct_mod_q(product[j]-product[j+n]);
        cntru_secure_wipe(product,sizeof(product));
        return;
    }
#ifdef CNTRU_AVX2_NTT
    cntru_ct_poly_mul_avx2(out,a,b,n);
#else
    uint32_t aa[2*n],bb[2*n];
    memset(aa,0,sizeof(aa));memset(bb,0,sizeof(bb));
    for(unsigned j=0;j<n;j++) {
        uint32_t x=(uint32_t)(int32_t)ct_center_q(a[j]),y=(uint32_t)(int32_t)ct_center_q(b[j]);
        x+=NTT_P&(0U-(x>>31));y+=NTT_P&(0U-(y>>31));
        aa[j]=multiply(x,NTT_R2);bb[j]=multiply(y,NTT_R2);
    }
    transform(aa,2*n,0);
    /* Pointer equality is public and permits a shorter schedule for squares. */
    if(a==b)memcpy(bb,aa,sizeof(bb));else transform(bb,2*n,0);
    for(unsigned j=0;j<2*n;j++)aa[j]=multiply(aa[j],bb[j]);
    transform(aa,2*n,1);
    for(unsigned j=0;j<n;j++) {
        uint32_t value=montgomery(subtract(aa[j],aa[j+n]));
        uint32_t high=ct_less_u32(NTT_P/2,value);
        int32_t lifted=(int32_t)value-(int32_t)(NTT_P*high);
        out[j]=ct_mod_q(lifted);
    }
    cntru_secure_wipe(aa,sizeof(aa));cntru_secure_wipe(bb,sizeof(bb));
#endif
}

static int16_t scalar_inverse(int16_t a) {
    int16_t result=1;
    for(int bit=8;bit>=0;bit--) {
        result=ct_mod_q((int32_t)result*result);
        if(((CNTRU_Q-2U)>>bit)&1U)result=ct_mod_q((int32_t)result*a);
    }
    return result;
}

/* If f=a(y)+xb(y), y=x^2, its norm is a(y)^2-yb(y)^2. In the quotient
 * y^(n/2)=-1 this has first coefficient a2[0]+b2[n/2-1]. */
static void make_norm(int16_t *norm,int16_t *a,int16_t *b,const int16_t *f,unsigned n) {
    unsigned half=n/2;
    int16_t a2[half],b2[half];
    for(unsigned j=0;j<half;j++){a[j]=f[2*j];b[j]=f[2*j+1];}
    cntru_ct_poly_mul_n(a2,a,a,half);
    cntru_ct_poly_mul_n(b2,b,b,half);
    norm[0]=ct_mod_q(a2[0]+b2[half-1]);
    for(unsigned j=1;j<half;j++)norm[j]=ct_mod_q(a2[j]-b2[j-1]);
    cntru_secure_wipe(a2,sizeof(a2));cntru_secure_wipe(b2,sizeof(b2));
}
uint32_t cntru_ct_poly_inverse_n(int16_t *out,const int16_t *f,unsigned n) {
    if(n==1) {
        int16_t a=ct_mod_q(f[0]);
        out[0]=scalar_inverse(a);
        return ct_nonzero_u32((uint32_t)a);
    }
    unsigned half=n/2;
    int16_t a[half],b[half],norm[half],inverse[half],even[half],odd[half];
    make_norm(norm,a,b,f,n);
    uint32_t valid=cntru_ct_poly_inverse_n(inverse,norm,half);
    cntru_ct_poly_mul_n(even,a,inverse,half);
    cntru_ct_poly_mul_n(odd,b,inverse,half);
    for(unsigned j=0;j<half;j++){out[2*j]=even[j];out[2*j+1]=ct_mod_q(-odd[j]);}
    cntru_secure_wipe(a,sizeof(a));cntru_secure_wipe(b,sizeof(b));
    cntru_secure_wipe(norm,sizeof(norm));cntru_secure_wipe(inverse,sizeof(inverse));
    cntru_secure_wipe(even,sizeof(even));cntru_secure_wipe(odd,sizeof(odd));
    return valid;
}
uint32_t cntru_ct_poly_unit_n(const int16_t *f,unsigned n) {
    if(n==1)return ct_nonzero_u32((uint32_t)ct_mod_q(f[0]));
    unsigned half=n/2;
    int16_t a[half],b[half],norm[half];
    make_norm(norm,a,b,f,n);
    uint32_t valid=cntru_ct_poly_unit_n(norm,half);
    cntru_secure_wipe(a,sizeof(a));cntru_secure_wipe(b,sizeof(b));cntru_secure_wipe(norm,sizeof(norm));
    return valid;
}
