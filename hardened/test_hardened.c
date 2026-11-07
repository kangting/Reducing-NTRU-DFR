#include "cntru.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(c) do { if (!(c)) { fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#c); return 1; } } while (0)

typedef struct { uint8_t bytes[131072]; size_t cursor; } test_tape;
static int read_tape(void *v, uint8_t *out, size_t count) {
    test_tape *t = v;
    if (count > sizeof(t->bytes)-t->cursor) return -1;
    memcpy(out,t->bytes+t->cursor,count);t->cursor+=count;return 0;
}
static int fail_rng(void *v, uint8_t *out, size_t count) {
    (void)v;(void)out;(void)count;return -1;
}

typedef struct {unsigned stage,f_trial,g_trial,fail_stage;int no_f,no_g;} pool_fixture;
static int fixture_rng(void *opaque,uint8_t *out,size_t length) {
    pool_fixture *f=opaque;
    unsigned stage=++f->stage;
    if(stage==1) {
        if(length!=65536)return -1;
        for(size_t j=0;j<length;j+=2){out[j]=0;out[j+1]=2;} /* f zero-atom word512 */
        if(!f->no_f){out[256*f->f_trial]=119;out[256*f->f_trial+1]=0;} /* -1 monomial */
    } else if(stage==2) {
        if(length!=512)return -1;
        for(size_t j=0;j<length;j+=2){out[j]=32;out[j+1]=2;} /* g zero-atom word544 */
        if(!f->no_g){out[256*f->g_trial]=120;out[256*f->g_trial+1]=7;} /* +1 word1912 */
    } else if(stage==3) {
        if(length!=32)return -1;
        memset(out,0xa5,length);
    } else return -1;
    return stage==f->fail_stage?-1:0;
}
static int all_zero(const void *value,size_t length) {
    const unsigned char *p=value;unsigned combined=0;
    for(size_t j=0;j<length;j++)combined|=p[j];
    return !combined;
}
static int counting_rng(void *opaque,uint8_t *out,size_t length) {
    unsigned *calls=opaque;
    (*calls)++;memset(out,0,length);return 0;
}
static int verify_invalid_pk_before_rng(void) {
    uint8_t bad_pk[495],ct[527],key[32],message[32]={0};
    memset(bad_pk,255,sizeof(bad_pk));memset(ct,0xa5,sizeof(ct));memset(key,0xa5,sizeof(key));
    unsigned calls=0;
    CHECK(cntru_encaps(ct,key,bad_pk,counting_rng,&calls)==-1);
    CHECK(calls==0&&all_zero(ct,sizeof(ct))&&all_zero(key,sizeof(key)));
    CHECK(cntru_base_encrypt(ct,bad_pk,message,counting_rng,&calls)==-1);
    CHECK(calls==0&&all_zero(ct,495));
    /* The historical randomized masked API obtains u before parsing pk. */
    CHECK(cntru_encrypt(ct,bad_pk,message,counting_rng,&calls)==-1);
    CHECK(calls==1&&all_zero(ct,sizeof(ct)));
    memset(ct,0xa5,sizeof(ct));
    CHECK(cntru_deterministic_encrypt(ct,bad_pk,message)==-1);
    CHECK(all_zero(ct,sizeof(ct)));
    return 0;
}
static int verify_base_decrypt_error_outputs(const cntru_sk *sk) {
    int16_t maximal[512];uint8_t boundary[495],core[495],out[32];
    for(unsigned j=0;j<512;j++)maximal[j]=210;
    CHECK(cntru_pack(boundary,maximal)==0);
    unsigned carry=1;
    for(unsigned j=0;j<495;j++){unsigned value=boundary[j]+carry;boundary[j]=(uint8_t)value;carry=value>>8;}
    for(unsigned pattern=0;pattern<3;pattern++) {
        if(pattern==0)memset(core,255,sizeof(core));
        else {
            memcpy(core,boundary,sizeof(core));
            if(pattern==2) {
                carry=1;
                for(unsigned j=0;j<495;j++){unsigned value=core[j]+carry;core[j]=(uint8_t)value;carry=value>>8;}
            }
        }
        for(unsigned fill=0;fill<2;fill++) {
            memset(out,fill?0x5a:0xa5,sizeof(out));
            CHECK(cntru_base_decrypt(out,sk,core)==-1);
            CHECK(all_zero(out,sizeof(out)));
        }
    }
    return 0;
}
static int verify_pool_failures(void) {
    uint8_t pk0[495],pk1[495];cntru_sk sk0,sk1;
    pool_fixture first={0,0,0,0,0,0};
    CHECK(cntru_keygen(pk0,&sk0,fixture_rng,&first)==0);
    CHECK(first.stage==3);
    CHECK(pk0[0]==210&&all_zero(pk0+1,494));
    CHECK(sk0.f[0]==-1&&all_zero(sk0.f+1,511*sizeof(sk0.f[0])));
    CHECK(sk0.fp_inverse[0]==1&&all_zero(sk0.fp_inverse+1,3*sizeof(uint64_t)));
    for(unsigned j=0;j<32;j++)CHECK(sk0.rejection_seed[j]==0xa5);
    pool_fixture last={0,255,1,0,0,0};
    CHECK(cntru_keygen(pk1,&sk1,fixture_rng,&last)==0);
    CHECK(last.stage==3&&!memcmp(pk0,pk1,495)&&!memcmp(&sk0,&sk1,sizeof(sk0)));
    for(unsigned mode=0;mode<5;mode++) {
        pool_fixture failure={0,0,0,mode<3?mode+1:0,mode==3,mode==4};
        memset(pk1,0x5a,sizeof(pk1));memset(&sk1,0x5a,sizeof(sk1));
        CHECK(cntru_keygen(pk1,&sk1,fixture_rng,&failure)==-1);
        CHECK(failure.stage==3&&all_zero(pk1,sizeof(pk1))&&all_zero(&sk1,sizeof(sk1)));
    }
    return 0;
}

static void oracle_mul(int16_t out[512], const int16_t a[512], const int16_t b[512]) {
    int64_t product[1024]={0};
    for(unsigned i=0;i<512;i++)for(unsigned j=0;j<512;j++)
        product[i+j]+=(int64_t)a[i]*b[j];
    for(unsigned i=0;i<512;i++) {
        int64_t v=(product[i]-product[i+512])%211;
        out[i]=(int16_t)(v+(v<0)*211);
    }
}
static int verify_arithmetic(void) {
    int16_t patterns[9][512], expected[512], actual[512], alias[512];
    for(unsigned j=0;j<512;j++) {
        patterns[0][j]=0;
        patterns[1][j]=210;
        patterns[2][j]=-210;
        patterns[3][j]=(j&1)?-210:210;
        patterns[4][j]=(int16_t)((int)(j%421)-210);
        patterns[5][j]=(j==511)?210:0;
        patterns[6][j]=(j==0)?-210:0;
        patterns[7][j]=1;
        patterns[8][j]=-1;
    }
    for(unsigned a=0;a<9;a++)for(unsigned b=0;b<9;b++) {
        oracle_mul(expected,patterns[a],patterns[b]);
        cntru_poly_mul(actual,patterns[a],patterns[b]);
        CHECK(!memcmp(actual,expected,sizeof(actual)));
        memcpy(alias,patterns[a],sizeof(alias));
        cntru_poly_mul(alias,alias,patterns[b]);
        CHECK(!memcmp(alias,expected,sizeof(alias)));
        memcpy(alias,patterns[b],sizeof(alias));
        cntru_poly_mul(alias,patterns[a],alias);
        CHECK(!memcmp(alias,expected,sizeof(alias)));
        if(a==b) {
            memcpy(alias,patterns[a],sizeof(alias));
            cntru_poly_mul(alias,alias,alias);
            CHECK(!memcmp(alias,expected,sizeof(alias)));
        }
    }
    uint8_t tape[32768];
    cntru_shake256(tape,sizeof(tape),(const uint8_t*)"signed polynomial tests",23);
    for(unsigned round=0;round<16;round++) {
        for(unsigned j=0;j<512;j++) {
            unsigned pos=round*2048+4*j;
            patterns[0][j]=(int16_t)((int)((tape[pos]|((unsigned)tape[pos+1]<<8))%421)-210);
            patterns[1][j]=(int16_t)((int)((tape[pos+2]|((unsigned)tape[pos+3]<<8))%421)-210);
        }
        oracle_mul(expected,patterns[0],patterns[1]);
        cntru_poly_mul(actual,patterns[0],patterns[1]);
        CHECK(!memcmp(actual,expected,sizeof(actual)));
    }
    /* Every monomial position and both extreme signs check negacyclic wrap. */
    for(unsigned amplitude=1;amplitude<=210;amplitude+=209)
    for(unsigned position=0;position<512;position++)for(int sign=-1;sign<=1;sign+=2) {
        memset(patterns[1],0,sizeof(patterns[1]));
        patterns[1][position]=(int16_t)(sign*(int)amplitude);
        for(unsigned j=0;j<512;j++) {
            int source=(int)j-(int)position;
            int v=sign*(int)amplitude*patterns[0][source<0?source+512:source]*(source<0?-1:1);
            v%=211;expected[j]=(int16_t)(v+(v<0)*211);
        }
        cntru_poly_mul(actual,patterns[0],patterns[1]);
        CHECK(!memcmp(actual,expected,sizeof(actual)));
    }
    for(unsigned j=0;j<512;j++)patterns[0][j]=210;
    uint8_t packed[495];
    CHECK(!cntru_pack(packed,patterns[0]));
    CHECK(!cntru_unpack(actual,packed));
    CHECK(!memcmp(actual,patterns[0],sizeof(actual)));
    /* q^512-1 is maximal canonical; adding one must be rejected. */
    unsigned carry=1;
    for(unsigned j=0;j<495;j++) {unsigned v=packed[j]+carry;packed[j]=(uint8_t)v;carry=v>>8;}
    CHECK(cntru_unpack(actual,packed)==-1);
    memset(packed,0,sizeof(packed));
    CHECK(!cntru_unpack(actual,packed));
    for(unsigned j=0;j<512;j++)CHECK(!actual[j]);
    return 0;
}
int main(void) {
    CHECK(verify_invalid_pk_before_rng()==0);
    CHECK(verify_pool_failures()==0);
    CHECK(verify_arithmetic()==0);
    uint8_t pk[495], ct[527], k1[32], k2[32], alternate[32], msg[32], core[495], u[32];
    static const uint8_t shake_empty[32] = {
        0x46,0xb9,0xdd,0x2b,0x0b,0xa8,0x8d,0x13,0x23,0x3b,0x3f,0xeb,0x74,0x3e,0xeb,0x24,
        0x3f,0xcd,0x52,0xea,0x62,0xb8,0x1b,0x82,0xb5,0x0c,0x27,0x64,0x6e,0xd5,0x76,0x2f};
    cntru_shake256(k1,32,NULL,0);
    CHECK(!memcmp(k1,shake_empty,32));
    cntru_sk sk;
    test_tape tape;
    cntru_shake256(tape.bytes,sizeof(tape.bytes),(const uint8_t*)"native selftest",15);
    tape.cursor=0;
    CHECK(cntru_keygen(pk,&sk,fail_rng,NULL)==-1);
    CHECK(cntru_keygen(pk,&sk,read_tape,&tape)==0);
    CHECK(!memcmp(pk,sk.public_key,495));
    CHECK(verify_base_decrypt_error_outputs(&sk)==0);
    size_t accepted_cursor=tape.cursor;
    for(unsigned i=0;i<32;i++) {
        memset(msg,(int)i,32);
        CHECK(cntru_base_encrypt(core,pk,msg,read_tape,&tape)==0);
        CHECK(cntru_base_decrypt(u,&sk,core)==0);
        CHECK(!memcmp(u,msg,32));
        CHECK(cntru_encrypt(ct,pk,msg,read_tape,&tape)==0);
        CHECK(cntru_decrypt(u,&sk,ct,527)==0);
        CHECK(!memcmp(u,msg,32));
        CHECK(cntru_decrypt(u,&sk,ct,526)==-1);
        CHECK(cntru_encaps(ct,k1,pk,read_tape,&tape)==0);
        CHECK(cntru_decaps(k2,&sk,ct,527)==0);
        CHECK(!memcmp(k1,k2,32));
        CHECK(cntru_decaps(alternate,&sk,ct,526)==0);
        CHECK(memcmp(k1,alternate,32));
        ct[i%527]^=1;
        CHECK(cntru_decaps(k2,&sk,ct,527)==0);
        CHECK(memcmp(k1,k2,32));
    }
    CHECK(cntru_decaps(k1,&sk,NULL,0)==0);
    CHECK(cntru_decaps(k2,&sk,(const uint8_t*)"",0)==0);
    CHECK(!memcmp(k1,k2,32));
    memset(core,255,495);
    int16_t coefficients[512];
    CHECK(cntru_unpack(coefficients,core)==-1);
    CHECK(cntru_base_decrypt(u,&sk,core)==-1);
    CHECK(cntru_encaps(ct,k1,core,read_tape,&tape)==-1);
    CHECK(cntru_deterministic_encrypt(ct,core,msg)==-1);
    memset(coefficients,0,sizeof(coefficients));
    coefficients[511]=211;
    CHECK(cntru_pack(core,coefficients)==-1);
    coefficients[511]=-1;
    CHECK(cntru_pack(core,coefficients)==-1);
    memset(coefficients,0,sizeof(coefficients));
    CHECK(cntru_poly_inv(coefficients,coefficients)==-1);
    printf("PASS: 6 prefilled BasePKE error-output cases; fixed-pool first/last selection,f/g exhaustion,3 RNG fault stages and wiped outputs;81 extreme/sign/zero polynomial pairs +alias,16 random products,2048 signed monomial wraps,q^512 boundary; SHAKE KAT,keygen(%zu bytes),32 base/masked-PKE and KEM round trips,malformed inputs\n",accepted_cursor);
    return 0;
}
