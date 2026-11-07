#include "ct_radix.h"
#include <limits.h>
#include <string.h>

#if !defined(__SIZEOF_INT128__)
#error "ct_radix requires an unsigned 128-bit integer type"
#endif
__extension__ typedef unsigned __int128 radix_u128;

static uint64_t high_product(uint64_t a, uint64_t b) {
    return (uint64_t)(((radix_u128)a*b)>>64);
}
static uint64_t nonzero(uint64_t x) { return (x | (0-x))>>63; }
static uint64_t barrier(uint64_t x) {
#if defined(__GNUC__) || defined(__clang__)
    __asm__ volatile("" : "+r"(x));
#else
    volatile uint64_t copy=x; x=copy;
#endif
    return x;
}
static void wipe(void *v,size_t n) {
    volatile uint8_t *p=v;
    while(n--) *p++=0;
}

/* Let B=2^64 and M=B+reciprocal=floor(B^2/d). For X=hi*B+lo,
 * q0=floor(X*M/B^2) is floor(X/d) or one less: X < d*B < B^2,
 * and 0 <= 1/d-M/B^2 < 1/B^2. The 192-bit product's high word is
 * hi+high(hi*v)+carry(low(hi*v)+lo+high(lo*v)). Subtracting q0*d
 * leaves [0,2d); one masked subtraction yields the exact remainder.
 * The 128-bit remainder is needed when d >= B/2. */
static inline uint64_t divrem(uint64_t *remainder,uint64_t hi,uint64_t lo,
                             uint64_t d,uint64_t reciprocal) {
    radix_u128 product=(radix_u128)hi*reciprocal;
    uint64_t middle=(uint64_t)product+lo;
    uint64_t carry=(uint64_t)(middle<(uint64_t)product);
    uint64_t next=middle+high_product(lo,reciprocal);
    carry+=(uint64_t)(next<middle);
    uint64_t quotient=hi+(uint64_t)(product>>64)+carry;
    radix_u128 multiple=(radix_u128)quotient*d;
    uint64_t low=lo-(uint64_t)multiple;
    uint64_t high=hi-(uint64_t)(multiple>>64)-(uint64_t)(lo<(uint64_t)multiple);
    uint64_t correction=nonzero(high)|(uint64_t)(low>=d);
    uint64_t mask=barrier(0-correction);
    *remainder=low-(d&mask);
    return quotient+correction;
}
uint64_t ct_radix_divrem(uint64_t *remainder,uint64_t hi,uint64_t lo,
                        uint64_t d,uint64_t reciprocal) {
    return divrem(remainder,hi,lo,d,reciprocal);
}

/* Public-only helpers used during plan construction. */
#ifndef CT_RADIX_STATIC_PLANS_ONLY
static unsigned bit_length(uint64_t x) {
    unsigned n=0;
    while(x) { n++; x>>=1; }
    return n;
}
static unsigned used_limbs(const uint64_t *a,unsigned count) {
    while(count && !a[count-1]) count--;
    return count;
}
static void multiply_public(uint64_t *a,unsigned count,uint64_t d) {
    uint64_t carry=0;
    for(unsigned i=0;i<count;i++) {
        radix_u128 value=(radix_u128)a[i]*d+carry;
        a[i]=(uint64_t)value; carry=(uint64_t)(value>>64);
    }
}
int ct_radix_plan_init(ct_radix_plan *p,uint32_t n,uint32_t q) {
    uint64_t scratch[CT_RADIX_MAX_LIMBS]={0};
    memset(p,0,sizeof(*p));
    if(!n || n>CT_RADIX_MAX_N || q<3 || q>32767 || !(q&1))return -1;
    p->n=n; p->q=q; p->divisor=1;
    while(p->divisor<=INT64_MAX/q) { p->divisor*=q; p->digits++; }
    p->chunks=(n+p->digits-1)/p->digits;
    if(p->chunks>CT_RADIX_MAX_CHUNKS)return -1;
    p->shift=64-bit_length(p->divisor);
    p->normalized_divisor=p->divisor<<p->shift;
    p->reciprocal=(uint64_t)(~(radix_u128)0/p->normalized_divisor);
    p->digit_reciprocal=UINT64_MAX/q+1;
    /* Exact q^n bound. All public arithmetic here may use division. */
    scratch[0]=1;
    for(unsigned i=0;i<n;i++)multiply_public(scratch,CT_RADIX_MAX_LIMBS,q);
    unsigned size=used_limbs(scratch,CT_RADIX_MAX_LIMBS);
    p->encoded_bytes=(64*(size-1)+bit_length(scratch[size-1])+7)/8;
    p->limbs=(p->encoded_bytes+7)/8;
    /* Packing processed coefficient count: first a partial top group. */
    memset(scratch,0,sizeof(scratch)); scratch[0]=1;
    unsigned top=n-(p->chunks-1)*p->digits;
    for(unsigned chunk=0;chunk<p->chunks;chunk++) {
        unsigned count=chunk? p->digits:top;
        for(unsigned i=0;i<count;i++)multiply_public(scratch,p->limbs,q);
        p->pack_limbs[chunk]=(uint16_t)used_limbs(scratch,p->limbs);
    }
    /* Max input is 2^(8*encoded_bytes)-1; repeated public division gives
     * exact upper bounds including noncanonical input. */
    for(unsigned i=0;i<p->limbs;i++)scratch[i]=UINT64_MAX;
    if(p->encoded_bytes&7)scratch[p->limbs-1]>>=64-8*(p->encoded_bytes&7);
    for(unsigned chunk=0;chunk<p->chunks;chunk++) {
        unsigned count=used_limbs(scratch,p->limbs);
        p->unpack_limbs[chunk]=(uint16_t)count;
        uint64_t remainder=0;
        for(unsigned i=count;i-->0;) {
            radix_u128 value=((radix_u128)remainder<<64)|scratch[i];
            scratch[i]=(uint64_t)(value/p->divisor);
            remainder=(uint64_t)(value%p->divisor);
        }
    }
    wipe(scratch,sizeof(scratch));
    return 0;
}
#endif

int ct_radix_pack(uint8_t *encoded,const int16_t *a,const ct_radix_plan *p) {
    uint64_t limbs[p->limbs];
    memset(limbs,0,sizeof(limbs));
    uint64_t bad=0;
    unsigned top=p->n-(p->chunks-1)*p->digits,processed=0;
    for(unsigned chunk=0;chunk<p->chunks;chunk++) {
        unsigned count=chunk?p->digits:top;
        unsigned start=p->n-processed-count;
        uint64_t carry=0,multiplier=1;
        for(unsigned k=0;k<count;k++) {
            uint32_t coefficient=(uint32_t)(int32_t)a[start+k];
            uint64_t valid=(uint64_t)(coefficient<p->q);
            bad|=1-valid;
            uint64_t mask=barrier(0-valid);
            carry+=((uint64_t)coefficient&mask)*multiplier;
            multiplier*=p->q;
        }
        for(unsigned j=0;j<p->pack_limbs[chunk];j++) {
            radix_u128 value=(radix_u128)limbs[j]*p->divisor+carry;
            limbs[j]=(uint64_t)value; carry=(uint64_t)(value>>64);
        }
        processed+=count;
    }
    uint64_t mask=barrier(nonzero(bad)-1);
    for(unsigned j=0;j<p->encoded_bytes;j++)
        encoded[j]=(uint8_t)((limbs[j>>3]>>((j&7)*8))&mask);
    wipe(limbs,sizeof(limbs));
    return -(int)nonzero(bad);
}
int ct_radix_unpack(int16_t *a,const uint8_t *encoded,const ct_radix_plan *p) {
    uint64_t limbs[p->limbs];
    memset(limbs,0,sizeof(limbs));
    for(unsigned j=0;j<p->encoded_bytes;j++)
        limbs[j>>3]|=(uint64_t)encoded[j]<<((j&7)*8);
    uint64_t bad=0;
    for(unsigned chunk=0;chunk<p->chunks;chunk++) {
        uint64_t remainder=0;
        for(unsigned j=p->unpack_limbs[chunk];j-->0;) {
            uint64_t lo=limbs[j],shift=p->shift;
            uint64_t hi=(remainder<<shift)|(lo>>(64-shift));
            uint64_t normalized_lo=lo<<shift;
            limbs[j]=divrem(&remainder,hi,normalized_lo,
                           p->normalized_divisor,p->reciprocal);
            remainder>>=shift;
        }
        for(unsigned k=0;k<p->digits;k++) {
            uint64_t quotient=high_product(remainder,p->digit_reciprocal);
            uint64_t product=quotient*p->q;
            uint64_t borrow=(uint64_t)(remainder<product);
            uint64_t digit=remainder-product+borrow*p->q;
            unsigned index=p->digits*chunk+k;
            if(index<p->n)a[index]=(int16_t)digit;else bad|=digit;
            remainder=quotient-borrow;
        }
    }
    for(unsigned j=0;j<p->limbs;j++)bad|=limbs[j];
    wipe(limbs,sizeof(limbs));
    return -(int)nonzero(bad);
}
