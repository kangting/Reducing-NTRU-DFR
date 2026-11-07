/* Prepared functional tests. Compiling this file does not execute a KEM. */
#include "cntru.h"
#include "double_decode.h"
#include "sampling_tables.h"
#include <stdio.h>
#include <string.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"FAIL line%d: %s\n",__LINE__,#x);return 1;}}while(0)
#define KEY_TAPE (CNTRU_F_POOL_BYTES+CNTRU_G_POOL_BYTES+CNTRU_MESSAGE_BYTES)
typedef struct {const uint8_t *data;size_t size,cursor,calls;} tape;
static uint8_t keybytes[KEY_TAPE];
static int read_tape(void *opaque,uint8_t *out,size_t count) {
    tape *t=opaque;if(count>t->size-t->cursor)return -1;
    memcpy(out,t->data+t->cursor,count);t->cursor+=count;t->calls++;return 0;
}
static int zero_rng(void *opaque,uint8_t *out,size_t count){(void)opaque;memset(out,0,count);return 0;}
static int fail_rng(void *opaque,uint8_t *out,size_t count){(void)opaque;memset(out,0x81,count);return -1;}
static int nonzero(const void *p,size_t size){const uint8_t*a=p;unsigned v=0;for(size_t i=0;i<size;i++)v|=a[i];return v!=0;}
static void put_word(uint8_t *p,uint32_t word){for(unsigned i=0;i<CNTRU_WORD_BYTES;i++)p[i]=(uint8_t)(word>>(8*i));}
static int fixed_key(uint8_t *pk,cntru_sk *sk,unsigned last) {
    memset(keybytes,0,sizeof(keybytes));
    put_word(keybytes+(last?(CNTRU_F_CANDIDATES-1)*CNTRU_SAMPLE_BYTES:0),cdf[0][0]);
    put_word(keybytes+CNTRU_F_POOL_BYTES+(last?CNTRU_SAMPLE_BYTES:0),cdf[1][0]);
    memset(keybytes+CNTRU_F_POOL_BYTES+CNTRU_G_POOL_BYTES,0xA5,CNTRU_MESSAGE_BYTES);
    tape t={keybytes,sizeof(keybytes),0,0};CHECK(cntru_keygen(pk,sk,read_tape,&t)==0);
    CHECK(t.cursor==sizeof(keybytes)&&t.calls==3);CHECK(sk->f[0]==1&&sk->h[0]==1&&pk[0]==1);
    for(unsigned i=1;i<CNTRU_N;i++)CHECK(sk->f[i]==0&&sk->h[i]==0);
    for(unsigned i=1;i<CNTRU_PK_BYTES;i++)CHECK(pk[i]==0);
    CHECK(sk->fp_inverse[0]==1);for(unsigned i=1;i<CNTRU_U_WORDS;i++)CHECK(sk->fp_inverse[i]==0);
    for(unsigned i=0;i<CNTRU_MESSAGE_BYTES;i++)CHECK(sk->rejection_seed[i]==0xA5);
    return 0;
}
static int codec_boundaries(void) {
    uint8_t bytes[CNTRU_PK_BYTES]={1},packed[CNTRU_PK_BYTES];int16_t a[CNTRU_N];
    /* Independent base256 construction of q^n, not the codec algorithm. */
    for(unsigned power=0;power<CNTRU_N;power++) {
        uint32_t carry=0;
        for(unsigned i=0;i<CNTRU_PK_BYTES;i++){uint32_t x=bytes[i]*CNTRU_Q+carry;bytes[i]=(uint8_t)x;carry=x>>8;}
        CHECK(carry==0);
    }
    CHECK(cntru_unpack(a,bytes)==-1);
    unsigned borrow=1;
    for(unsigned i=0;i<CNTRU_PK_BYTES;i++){unsigned old=bytes[i];bytes[i]=(uint8_t)(old-borrow);borrow&=(old==0);}
    CHECK(cntru_unpack(a,bytes)==0);for(unsigned i=0;i<CNTRU_N;i++)CHECK(a[i]==CNTRU_Q-1);
    CHECK(cntru_pack(packed,a)==0&&memcmp(bytes,packed,sizeof(bytes))==0);
    a[CNTRU_N-1]=-1;memset(packed,0xA5,sizeof(packed));CHECK(cntru_pack(packed,a)==-1&&!nonzero(packed,sizeof(packed)));
    return 0;
}
/* A nontrivial leaf inverse catches a too-short q-2 exponent schedule.
 * Forced f=g=1 key fixtures exercise only the trivial inverse of1. */
static int constant_inverse(void) {
    int16_t a[CNTRU_N]={0},inverse[CNTRU_N],product[CNTRU_N];
    a[0]=2;
    CHECK(cntru_poly_inv(inverse,a)==0);
    CHECK(inverse[0]==(CNTRU_Q+1)/2);
    for(unsigned i=1;i<CNTRU_N;i++)CHECK(inverse[i]==0);
    cntru_poly_mul(product,a,inverse);
    CHECK(product[0]==1);
    for(unsigned i=1;i<CNTRU_N;i++)CHECK(product[i]==0);
    return 0;
}
static int sampler_residues(void) {
    int16_t r[CNTRU_N],m[CNTRU_N];uint8_t u[CNTRU_U_BYTES],rho[CNTRU_RHO_BYTES];
    for(unsigned pattern=0;pattern<4;pattern++) {
        memset(u,(int)(pattern*0x55),sizeof(u));for(unsigned j=0;j<sizeof(rho);j++)rho[j]=(uint8_t)(29*j+pattern);
        tape t={rho,sizeof(rho),0,0};CHECK(cntru_sample_rm(r,m,u,read_tape,&t)==0&&t.cursor==sizeof(rho)&&t.calls==1);
        for(unsigned j=0;j<CNTRU_HALF;j++) {
#if CNTRU_DOUBLE
            unsigned index=j%CNTRU_BLOCKS;
#else
            unsigned index=j;
#endif
            unsigned expected=(u[index>>3]>>(index&7))&1U;
            CHECK(((unsigned)(m[j]+m[j+CNTRU_HALF])&1U)==expected);
        }
    }
    return 0;
}
#if CNTRU_DOUBLE
static int correction_cases(const cntru_sk *sk) {
    int16_t centered[CNTRU_N]={0},c[CNTRU_N];uint64_t bits[CNTRU_U_WORDS],expected[CNTRU_U_WORDS]={0};
    uint8_t core[CNTRU_CORE_BYTES],u[CNTRU_U_BYTES];const unsigned group=7;
    centered[group]=3;centered[group+CNTRU_BLOCKS]=-3;centered[group+2*CNTRU_BLOCKS]=1;
    CHECK(cntru_double_residue(bits,centered)==1);
    expected[group>>6]|=UINT64_C(1)<<(group&63);
    unsigned other=group+CNTRU_BLOCKS;expected[other>>6]|=UINT64_C(1)<<(other&63);
    CHECK(!memcmp(bits,expected,sizeof(bits))); /* First index wins the magnitude tie. */
    memset(centered,0,sizeof(centered));centered[1]=centered[2]=1;
    CHECK(cntru_double_residue(bits,centered)==0);
    /* Construct a canonical ciphertext with EXACT desired P*f*c centered
     * vector, using the independently forced f=1 fixture and P^-1 formula. */
    for(unsigned j=0;j<CNTRU_HALF;j++) {
        int32_t a=centered[j],b=centered[j+CNTRU_HALF],inverse=(CNTRU_Q+1)/2;
        c[j]=(int16_t)((inverse*(a+b))%CNTRU_Q);
        c[j+CNTRU_HALF]=(int16_t)(((inverse*(b-a))%CNTRU_Q+CNTRU_Q)%CNTRU_Q);
    }
    CHECK(cntru_pack(core,c)==0);memset(u,0xA5,sizeof(u));
    CHECK(cntru_base_decrypt(u,sk,core)==-1&&!nonzero(u,sizeof(u)));
    return 0;
}
#endif
int main(void) {
    uint8_t pk[CNTRU_PK_BYTES],ct[CNTRU_CT_BYTES],again[CNTRU_CT_BYTES],u[CNTRU_U_BYTES],v[CNTRU_U_BYTES];
    uint8_t key[CNTRU_KEY_BYTES],recovered[CNTRU_KEY_BYTES],message[CNTRU_MESSAGE_BYTES],out[CNTRU_MESSAGE_BYTES];cntru_sk sk;
    CHECK(codec_boundaries()==0&&constant_inverse()==0&&sampler_residues()==0);CHECK(fixed_key(pk,&sk,0)==0&&fixed_key(pk,&sk,1)==0);
#if CNTRU_DOUBLE
    CHECK(correction_cases(&sk)==0);
#endif
    memset(u,0xA5,sizeof(u));CHECK(cntru_base_encrypt(ct,pk,u,zero_rng,NULL)==0);
    CHECK(cntru_base_decrypt(v,&sk,ct)==0&&!memcmp(u,v,sizeof(u)));
    for(unsigned i=0;i<8;i++) {
        memset(message,(int)(17*i),sizeof(message));tape mt={message,sizeof(message),0,0};
        CHECK(cntru_encaps(ct,key,pk,read_tape,&mt)==0&&mt.cursor==sizeof(message));
        CHECK(cntru_deterministic_encrypt(again,pk,message)==0&&!memcmp(again,ct,sizeof(ct)));
        CHECK(cntru_decaps(recovered,&sk,ct,sizeof(ct))==0&&!memcmp(key,recovered,sizeof(key)));
        ct[CNTRU_CORE_BYTES]^=1;CHECK(cntru_decaps(recovered,&sk,ct,sizeof(ct))==0&&memcmp(key,recovered,sizeof(key)));
        CHECK(cntru_decaps(recovered,&sk,NULL,0)==0);
    }
    CHECK(cntru_encrypt(ct,pk,message,zero_rng,NULL)==0&&cntru_decrypt(out,&sk,ct,sizeof(ct))==0&&!memcmp(out,message,sizeof(message)));
    memset(ct,0xFF,CNTRU_CORE_BYTES);memset(v,0xA5,sizeof(v));CHECK(cntru_base_decrypt(v,&sk,ct)==-1&&!nonzero(v,sizeof(v)));
    memset(ct+CNTRU_CORE_BYTES,0,CNTRU_MESSAGE_BYTES);memset(out,0xA5,sizeof(out));CHECK(cntru_decrypt(out,&sk,ct,sizeof(ct))==-1&&!nonzero(out,sizeof(out)));
    memset(&sk,0xA5,sizeof(sk));memset(pk,0xA5,sizeof(pk));CHECK(cntru_keygen(pk,&sk,fail_rng,NULL)==-1&&!nonzero(pk,sizeof(pk))&&!nonzero(&sk,sizeof(sk)));
    memset(&sk,0xA5,sizeof(sk));CHECK(cntru_keygen(pk,&sk,zero_rng,NULL)==-1&&!nonzero(pk,sizeof(pk))&&!nonzero(&sk,sizeof(sk)));
    puts("PASS: prepared family functional tests; not a security/DFR/CT certificate");return 0;
}
