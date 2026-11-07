#include "ct_radix.h"
#include "ct_radix_generated.h"
#include <assert.h>
#include <inttypes.h>
#include <stdio.h>
#include <string.h>
__extension__ typedef unsigned __int128 u128;
static uint64_t state=UINT64_C(0x725a1ce408b956d3);
static uint64_t random_word(void) {
    state^=state<<13; state^=state>>7; state^=state<<17; return state;
}
static void division_tests(void) {
    for(unsigned t=0;t<1000000;t++) {
        uint64_t d=random_word()|UINT64_C(0x8000000000000001);
        uint64_t reciprocal=(uint64_t)(~(u128)0/d);
        uint64_t hi=random_word()%d,lo=random_word(),rem;
        uint64_t quotient=ct_radix_divrem(&rem,hi,lo,d,reciprocal);
        u128 x=((u128)hi<<64)|lo;
        assert(quotient==(uint64_t)(x/d) && rem==(uint64_t)(x%d));
        const uint64_t highs[]={0,1,d/2,d-2,d-1};
        const uint64_t lows[]={0,1,UINT64_MAX-1,UINT64_MAX};
        if(t<1000)for(unsigned i=0;i<5;i++)for(unsigned j=0;j<4;j++) {
            x=((u128)highs[i]<<64)|lows[j];
            quotient=ct_radix_divrem(&rem,highs[i],lows[j],d,reciprocal);
            assert(quotient==(uint64_t)(x/d) && rem==(uint64_t)(x%d));
        }
    }
}
static void roundtrip(unsigned n,unsigned q) {
    ct_radix_plan p;
    int16_t a[CT_RADIX_MAX_N],b[CT_RADIX_MAX_N];
    uint8_t encoded[CT_RADIX_MAX_LIMBS*8];
    assert(ct_radix_plan_init(&p,n,q)==0);
    const ct_radix_plan *generated=NULL;
    if(n==512 && q==211)generated=&ct_radix_n512_q211;
    if(n==1024 && q==307)generated=&ct_radix_n1024_q307;
    if(n==1024 && q==331)generated=&ct_radix_n1024_q331;
    if(n==1024 && q==373)generated=&ct_radix_n1024_q373;
    if(generated) {
        assert(p.n==generated->n && p.q==generated->q);
        assert(p.encoded_bytes==generated->encoded_bytes && p.limbs==generated->limbs);
        assert(p.digits==generated->digits && p.chunks==generated->chunks);
        assert(p.shift==generated->shift && p.divisor==generated->divisor);
        assert(p.normalized_divisor==generated->normalized_divisor);
        assert(p.reciprocal==generated->reciprocal);
        assert(p.digit_reciprocal==generated->digit_reciprocal);
        assert(memcmp(p.pack_limbs,generated->pack_limbs,sizeof(p.pack_limbs))==0);
        assert(memcmp(p.unpack_limbs,generated->unpack_limbs,sizeof(p.unpack_limbs))==0);
    }
    for(unsigned t=0;t<32;t++) {
        for(unsigned i=0;i<n;i++)a[i]=(int16_t)(random_word()%q);
        assert(ct_radix_pack(encoded,a,&p)==0);
        assert(ct_radix_unpack(b,encoded,&p)==0);
        assert(memcmp(a,b,n*sizeof(*a))==0);
    }
    memset(a,0,n*sizeof(*a));
    assert(ct_radix_pack(encoded,a,&p)==0);
    for(unsigned i=0;i<p.encoded_bytes;i++)assert(encoded[i]==0);
    for(unsigned i=0;i<n;i++)a[i]=(int16_t)(q-1);
    assert(ct_radix_pack(encoded,a,&p)==0);
    assert(ct_radix_unpack(b,encoded,&p)==0);
    assert(memcmp(a,b,n*sizeof(*a))==0);
    for(unsigned i=0;i<p.encoded_bytes;i++)if(++encoded[i])break;
    assert(ct_radix_unpack(b,encoded,&p)==-1); /* q^n */
    memset(encoded,255,p.encoded_bytes);
    assert(ct_radix_unpack(b,encoded,&p)==-1);
    const int invalids[]={-32768,-1,(int)q,32767};
    for(unsigned j=0;j<sizeof(invalids)/sizeof(*invalids);j++) {
        if(invalids[j]<(int)q && invalids[j]>=0)continue;
        for(unsigned i=0;i<n;i++)a[i]=0;
        a[n/2]=(int16_t)invalids[j];
        memset(encoded,165,p.encoded_bytes);
        assert(ct_radix_pack(encoded,a,&p)==-1);
        for(unsigned i=0;i<p.encoded_bytes;i++)assert(encoded[i]==0);
    }
    unsigned pack=0,unpack=0;
    for(unsigned i=0;i<p.chunks;i++) { pack+=p.pack_limbs[i]; unpack+=p.unpack_limbs[i]; }
    printf("n=%u q=%u bytes=%u digits=%u chunks=%u pack_visits=%u unpack_visits=%u\n",
           n,q,p.encoded_bytes,p.digits,p.chunks,pack,unpack);
}
int main(void) {
    division_tests();
    roundtrip(512,211); roundtrip(1024,307); roundtrip(1024,331); roundtrip(1024,373);
    const unsigned ns[]={1,2,3,7,8,9,31,64,65,257,4096};
    const unsigned qs[]={3,5,127,257,32767};
    for(unsigned i=0;i<sizeof(ns)/sizeof(*ns);i++)
        for(unsigned j=0;j<sizeof(qs)/sizeof(*qs);j++)roundtrip(ns[i],qs[j]);
    puts("ct_radix arithmetic and roundtrip tests passed");
    return 0;
}
