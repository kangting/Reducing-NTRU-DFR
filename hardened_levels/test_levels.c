#include "cntru.h"
#include "sampling_tables.h"
#include <stdio.h>
#include <string.h>

#define CHECK(c) do{if(!(c)){fprintf(stderr,"FAIL q%d line%d:%s\n",CNTRU_Q,__LINE__,#c);return 1;}}while(0)
static int zero(const void *v,size_t n){const uint8_t *p=v;unsigned x=0;for(size_t j=0;j<n;j++)x|=p[j];return x==0;}
typedef struct{uint8_t bytes[262144];size_t cursor;} tape;
static int read_tape(void *opaque,uint8_t *out,size_t length){tape *t=opaque;if(length>sizeof(t->bytes)-t->cursor)return -1;memcpy(out,t->bytes+t->cursor,length);t->cursor+=length;return 0;}
typedef struct{unsigned stage,f_trial,g_trial,fail_stage,no_f,no_g;} fixture;
static void set_word(uint8_t *where,unsigned value){where[0]=(uint8_t)value;where[1]=(uint8_t)(value>>8);}
static int fixture_rng(void *opaque,uint8_t *out,size_t length){
    fixture *f=opaque;unsigned stage=++f->stage;
    if(stage==1){
        if(length!=CNTRU_F_POOL_BYTES)return -1;
        for(size_t j=0;j<length;j+=2)set_word(out+j,cdf[0][7]);
        if(!f->no_f)set_word(out+CNTRU_SAMPLE_BYTES*f->f_trial,cdf[0][0]);
    }else if(stage==2){
        if(length!=CNTRU_G_POOL_BYTES)return -1;
        for(size_t j=0;j<length;j+=2)set_word(out+j,cdf[1][7]);
        if(!f->no_g)set_word(out+CNTRU_SAMPLE_BYTES*f->g_trial,cdf[1][14]);
    }else if(stage==3){if(length!=32)return -1;memset(out,0xa5,length);}else return -1;
    return stage==f->fail_stage?-1:0;
}
static int test_pool(void){
    uint8_t p0[CNTRU_PK_BYTES],p1[CNTRU_PK_BYTES];cntru_sk s0,s1;
    fixture first={0,0,0,0,0,0},last={0,255,1,0,0,0};
    CHECK(!cntru_keygen(p0,&s0,fixture_rng,&first)&&first.stage==3);
    CHECK(s0.f[0]==-1&&zero(s0.f+1,(CNTRU_N-1)*sizeof(int16_t)));
    int16_t expected[CNTRU_N]={0};expected[0]=CNTRU_Q-1;
    uint8_t packed[CNTRU_PK_BYTES];CHECK(!cntru_pack(packed,expected));CHECK(!memcmp(p0,packed,sizeof(p0)));
    CHECK(!cntru_keygen(p1,&s1,fixture_rng,&last)&&last.stage==3);
    CHECK(!memcmp(p0,p1,sizeof(p0))&&!memcmp(&s0,&s1,sizeof(s0)));
    for(unsigned mode=0;mode<5;mode++){
        fixture bad={0,0,0,mode<3?mode+1:0,mode==3,mode==4};
        memset(p1,0x5a,sizeof(p1));memset(&s1,0x5a,sizeof(s1));
        CHECK(cntru_keygen(p1,&s1,fixture_rng,&bad)==-1&&bad.stage==3);
        CHECK(zero(p1,sizeof(p1))&&zero(&s1,sizeof(s1)));
    }
    return 0;
}
static void schoolbook(int16_t *out,const int16_t *a,const int16_t *b){
    int64_t product[2*CNTRU_N]={0};
    for(unsigned i=0;i<CNTRU_N;i++)for(unsigned j=0;j<CNTRU_N;j++)product[i+j]+=(int64_t)a[i]*b[j];
    for(unsigned j=0;j<CNTRU_N;j++){int64_t v=(product[j]-product[j+CNTRU_N])%CNTRU_Q;out[j]=(int16_t)(v+(v<0)*CNTRU_Q);}
}
static int test_math(void){
    int16_t patterns[9][CNTRU_N],expected[CNTRU_N],actual[CNTRU_N],alias[CNTRU_N];
    for(unsigned j=0;j<CNTRU_N;j++){
        patterns[0][j]=0;patterns[1][j]=CNTRU_Q-1;patterns[2][j]=1-CNTRU_Q;
        patterns[3][j]=(j&1)?1-CNTRU_Q:CNTRU_Q-1;
        patterns[4][j]=(int16_t)((int)(j%(2*CNTRU_Q-1))-(CNTRU_Q-1));
        patterns[5][j]=(j==CNTRU_N-1)?CNTRU_Q-1:0;patterns[6][j]=(j==0)?1-CNTRU_Q:0;
        patterns[7][j]=CNTRU_Q/2;patterns[8][j]=-CNTRU_Q/2;
    }
    for(unsigned a=0;a<9;a++)for(unsigned b=0;b<9;b++){
        schoolbook(expected,patterns[a],patterns[b]);cntru_poly_mul(actual,patterns[a],patterns[b]);
        CHECK(!memcmp(expected,actual,sizeof(actual)));
        memcpy(alias,patterns[a],sizeof(alias));cntru_poly_mul(alias,alias,patterns[b]);CHECK(!memcmp(alias,expected,sizeof(alias)));
        memcpy(alias,patterns[b],sizeof(alias));cntru_poly_mul(alias,patterns[a],alias);CHECK(!memcmp(alias,expected,sizeof(alias)));
    }
    uint8_t bytes[CNTRU_N*4];cntru_shake256(bytes,sizeof(bytes),(const uint8_t*)"levels signed products",22);
    for(unsigned iteration=0;iteration<16;iteration++){
        cntru_shake256(bytes,sizeof(bytes),bytes,sizeof(bytes));
        for(unsigned j=0;j<CNTRU_N;j++){
            patterns[0][j]=(int16_t)((int)((bytes[4*j]|((unsigned)bytes[4*j+1]<<8))%(2*CNTRU_Q-1))-(CNTRU_Q-1));
            patterns[1][j]=(int16_t)((int)((bytes[4*j+2]|((unsigned)bytes[4*j+3]<<8))%(2*CNTRU_Q-1))-(CNTRU_Q-1));
        }
        schoolbook(expected,patterns[0],patterns[1]);cntru_poly_mul(actual,patterns[0],patterns[1]);CHECK(!memcmp(actual,expected,sizeof(actual)));
    }
    for(unsigned amplitude=1;amplitude<=CNTRU_Q-1;amplitude+=CNTRU_Q-2)
    for(unsigned position=0;position<CNTRU_N;position++)for(int sign=-1;sign<=1;sign+=2){
        memset(patterns[1],0,sizeof(patterns[1]));patterns[1][position]=(int16_t)(sign*(int)amplitude);
        for(unsigned j=0;j<CNTRU_N;j++){
            int source=(int)j-(int)position;int v=sign*(int)amplitude*patterns[0][source<0?source+CNTRU_N:source]*(source<0?-1:1);
            v%=CNTRU_Q;expected[j]=(int16_t)(v+(v<0)*CNTRU_Q);
        }
        cntru_poly_mul(actual,patterns[0],patterns[1]);CHECK(!memcmp(actual,expected,sizeof(actual)));
    }
    memset(actual,0,sizeof(actual));CHECK(cntru_poly_inv(alias,actual)==-1&&zero(alias,sizeof(alias)));
    actual[0]=-1;CHECK(!cntru_poly_inv(alias,actual)&&alias[0]==CNTRU_Q-1&&zero(alias+1,(CNTRU_N-1)*sizeof(int16_t)));
    return 0;
}
static int test_codec_and_errors(const cntru_sk *sk){
    int16_t a[CNTRU_N],decoded[CNTRU_N];uint8_t maximum[CNTRU_PK_BYTES],invalid[CNTRU_PK_BYTES],out[CNTRU_U_BYTES];
    for(unsigned j=0;j<CNTRU_N;j++)a[j]=CNTRU_Q-1;
    CHECK(!cntru_pack(maximum,a)&&!cntru_unpack(decoded,maximum)&&!memcmp(a,decoded,sizeof(a)));
    unsigned carry=1;
    for(unsigned j=0;j<CNTRU_PK_BYTES;j++){unsigned x=maximum[j]+carry;maximum[j]=(uint8_t)x;carry=x>>8;}
    for(unsigned pattern=0;pattern<3;pattern++){
        if(pattern==0)memset(invalid,255,sizeof(invalid));else{memcpy(invalid,maximum,sizeof(invalid));if(pattern==2)invalid[0]++;}
        CHECK(cntru_unpack(decoded,invalid)==-1);memset(out,0xa5,sizeof(out));
        CHECK(cntru_base_decrypt(out,sk,invalid)==-1&&zero(out,sizeof(out)));
    }
    memset(a,0,sizeof(a));a[CNTRU_N-1]=CNTRU_Q;CHECK(cntru_pack(invalid,a)==-1&&zero(invalid,sizeof(invalid)));
    return 0;
}
int main(void){
    CHECK(!test_pool());CHECK(!test_math());
    static const uint8_t kat[32]={0x46,0xb9,0xdd,0x2b,0x0b,0xa8,0x8d,0x13,0x23,0x3b,0x3f,0xeb,0x74,0x3e,0xeb,0x24,0x3f,0xcd,0x52,0xea,0x62,0xb8,0x1b,0x82,0xb5,0x0c,0x27,0x64,0x6e,0xd5,0x76,0x2f};
    uint8_t hash[32];cntru_shake256(hash,32,NULL,0);CHECK(!memcmp(hash,kat,32));
    tape t;t.cursor=0;cntru_shake256(t.bytes,sizeof(t.bytes),(const uint8_t*)"levels selftest",15);
    uint8_t pk[CNTRU_PK_BYTES],ct[CNTRU_CT_BYTES],core[CNTRU_CORE_BYTES],internal[CNTRU_U_BYTES],recovered[CNTRU_U_BYTES],message[32],k0[32],k1[32];cntru_sk sk;
    CHECK(!cntru_keygen(pk,&sk,read_tape,&t)&&t.cursor==CNTRU_F_POOL_BYTES+CNTRU_G_POOL_BYTES+32);
    CHECK(!test_codec_and_errors(&sk));
    for(unsigned iteration=0;iteration<16;iteration++){
        memset(internal,(int)(iteration*17),sizeof(internal));memset(message,(int)(iteration*13),sizeof(message));
        CHECK(!cntru_base_encrypt(core,pk,internal,read_tape,&t));CHECK(!cntru_base_decrypt(recovered,&sk,core));CHECK(!memcmp(internal,recovered,sizeof(internal)));
        CHECK(!cntru_encrypt(ct,pk,message,read_tape,&t));CHECK(!cntru_decrypt(recovered,&sk,ct,sizeof(ct)));CHECK(!memcmp(recovered,message,32));
        CHECK(!cntru_encaps(ct,k0,pk,read_tape,&t));CHECK(!cntru_decaps(k1,&sk,ct,sizeof(ct)));CHECK(!memcmp(k0,k1,32));
        ct[CNTRU_CORE_BYTES]^=1;CHECK(!cntru_decaps(k1,&sk,ct,sizeof(ct))&&memcmp(k0,k1,32));
    }
    CHECK(!cntru_decaps(k0,&sk,NULL,0));CHECK(!cntru_decaps(k1,&sk,(const uint8_t*)"",0)&&!memcmp(k0,k1,32));
    printf("PASS q%d: exact sizes/fixed pool/fault wipes,81 full-range pairs+aliases,16 random products,4096 signed monomial wraps,codec q^1024 boundaries,64-byte error wipe,16 BasePKE/ACWC0/KEM roundtrips\n",CNTRU_Q);
    return 0;
}
