#define _POSIX_C_SOURCE 200809L
#include "cntru.h"
#include "ct_util.h"
#include "ct_ntt.h"
#include "../common/ct_lookup.h"
#include "radix.h"
#include <errno.h>
#include <string.h>
#include <sys/random.h>
#include "sampling_tables.h"

static uint64_t rol64(uint64_t x, unsigned n) {
    return (x << n) | (x >> (64 - n));
}

static void keccak(uint64_t s[25]) {
    static const uint64_t rc[24] = {
        UINT64_C(0x0000000000000001),UINT64_C(0x0000000000008082),
        UINT64_C(0x800000000000808a),UINT64_C(0x8000000080008000),
        UINT64_C(0x000000000000808b),UINT64_C(0x0000000080000001),
        UINT64_C(0x8000000080008081),UINT64_C(0x8000000000008009),
        UINT64_C(0x000000000000008a),UINT64_C(0x0000000000000088),
        UINT64_C(0x0000000080008009),UINT64_C(0x000000008000000a),
        UINT64_C(0x000000008000808b),UINT64_C(0x800000000000008b),
        UINT64_C(0x8000000000008089),UINT64_C(0x8000000000008003),
        UINT64_C(0x8000000000008002),UINT64_C(0x8000000000000080),
        UINT64_C(0x000000000000800a),UINT64_C(0x800000008000000a),
        UINT64_C(0x8000000080008081),UINT64_C(0x8000000000008080),
        UINT64_C(0x0000000080000001),UINT64_C(0x8000000080008008)};
    static const unsigned rotation[24] = {1,3,6,10,15,21,28,36,45,55,2,14,27,41,56,8,25,43,62,18,39,61,20,44};
    static const unsigned permutation[24] = {10,7,11,17,18,3,5,16,8,21,24,4,15,23,19,13,12,2,20,14,22,9,6,1};
    uint64_t b[5];
    for (unsigned round = 0; round < 24; round++) {
        for (unsigned x = 0; x < 5; x++)
            b[x] = s[x] ^ s[x+5] ^ s[x+10] ^ s[x+15] ^ s[x+20];
        for (unsigned x = 0; x < 5; x++) {
            uint64_t d = b[(x+4)%5] ^ rol64(b[(x+1)%5], 1);
            for (unsigned y = 0; y < 25; y += 5) s[x+y] ^= d;
        }
        uint64_t t = s[1];
        for (unsigned j = 0; j < 24; j++) {
            unsigned p = permutation[j];
            uint64_t saved = s[p];
            s[p] = rol64(t, rotation[j]);
            t = saved;
        }
        for (unsigned y = 0; y < 25; y += 5) {
            for (unsigned x = 0; x < 5; x++) b[x] = s[y+x];
            for (unsigned x = 0; x < 5; x++)
                s[y+x] = b[x] ^ ((~b[(x+1)%5]) & b[(x+2)%5]);
        }
        s[0] ^= rc[round];
    }
}

typedef struct {uint64_t s[25];unsigned pos;} shake_ctx;
static void absorb(shake_ctx *ctx,const uint8_t *in,size_t len) {
    for(size_t j=0;j<len;j++) {
        ctx->s[ctx->pos>>3]^=(uint64_t)in[j]<<((ctx->pos&7)*8);
        if(++ctx->pos==136){keccak(ctx->s);ctx->pos=0;}
    }
}
static void squeeze(shake_ctx *ctx,uint8_t *out,size_t len) {
    ctx->s[ctx->pos>>3]^=UINT64_C(0x1f)<<((ctx->pos&7)*8);
    ctx->s[16]^=UINT64_C(0x8000000000000000);
    keccak(ctx->s);ctx->pos=0;
    for(size_t j=0;j<len;j++) {
        out[j]=(uint8_t)(ctx->s[ctx->pos>>3]>>((ctx->pos&7)*8));
        if(++ctx->pos==136 && j+1<len){keccak(ctx->s);ctx->pos=0;}
    }
}
void cntru_shake256(uint8_t *out,size_t out_len,const uint8_t *in,size_t in_len) {
    shake_ctx ctx={{0},0};absorb(&ctx,in,in_len);squeeze(&ctx,out,out_len);
    cntru_secure_wipe(&ctx,sizeof(ctx));
}
static void absorb_length(shake_ctx *ctx,size_t length) {
    uint8_t bytes[8];
    for(unsigned j=0;j<8;j++)bytes[j]=(uint8_t)((uint64_t)length>>(8*j));
    absorb(ctx,bytes,8);
}
static void absorb_part(shake_ctx *ctx,const uint8_t *part,size_t length) {
    absorb_length(ctx,length);absorb(ctx,part,length);
}
static void hash_start(shake_ctx *ctx,uint8_t tag,const uint8_t pk[495]) {
    static const uint8_t version[]="Complementary-NTRU-ACWC0-FO-v1";
    static const uint8_t parameters[]="n512-q211-P1+x256-block17-v1";
    memset(ctx,0,sizeof(*ctx));
    absorb_part(ctx,&tag,1);
    absorb_length(ctx,24+sizeof(version)-1+sizeof(parameters)-1+495);
    absorb_part(ctx,version,sizeof(version)-1);
    absorb_part(ctx,parameters,sizeof(parameters)-1);
    absorb_part(ctx,pk,495);
}
static void mask_hash(uint8_t out[32],const uint8_t pk[495],const uint8_t u[32]) {
    shake_ctx ctx;hash_start(&ctx,'F',pk);absorb_part(&ctx,u,32);squeeze(&ctx,out,32);
    cntru_secure_wipe(&ctx,sizeof(ctx));
}
static void key_hash(uint8_t out[32],const uint8_t pk[495],const uint8_t *ct,size_t ct_len,const uint8_t secret[32]) {
    shake_ctx ctx;hash_start(&ctx,'H',pk);absorb_part(&ctx,ct,ct_len);absorb_part(&ctx,secret,32);
    squeeze(&ctx,out,32);cntru_secure_wipe(&ctx,sizeof(ctx));
}

int cntru_randombytes(void *unused,uint8_t *out,size_t length) {
    (void)unused;
    uint8_t *original=out;size_t count=length;
    while(length) {
        ssize_t got=getrandom(out,length,0);
        if(got<0){if(errno==EINTR)continue;cntru_secure_wipe(original,count);return -1;}
        if(got==0){cntru_secure_wipe(original,count);return -1;}
        out+=(size_t)got;length-=(size_t)got;
    }
    return 0;
}

/* Shared fixed-schedule64-bit radix codec; the immutable public plan
 * preserves the complete canonical wire integer and malformed-input rules. */
int cntru_pack(uint8_t encoded[CNTRU_PK_BYTES],const int16_t a[CNTRU_N]) {
    return ct_radix_pack(encoded,a,&CNTRU_RADIX_PLAN);
}
int cntru_unpack(int16_t a[CNTRU_N],const uint8_t encoded[CNTRU_PK_BYTES]) {
    return ct_radix_unpack(a,encoded,&CNTRU_RADIX_PLAN);
}
void cntru_poly_mul(int16_t out[512],const int16_t a[512],const int16_t b[512]) {
    cntru_ct_poly_mul_n(out,a,b,512);
}
int cntru_poly_inv(int16_t out[512],const int16_t a[512]) {
    return (int)cntru_ct_poly_inverse_n(out,a,512)-1;
}

static void f2_multiply(uint64_t out[4],const uint64_t a[4],const uint64_t b[4]) {
    uint64_t result[4]={0};
    for(unsigned word=0;word<4;word++)for(unsigned bit=0;bit<64;bit++) {
        uint64_t mask=ct_barrier_u64(UINT64_C(0)-((a[word]>>bit)&1));
        for(unsigned j=0;j<4;j++) {
            unsigned k=(j+4-word)&3;
            uint64_t v=b[k]<<bit;
            if(bit)v|=b[(k+3)&3]>>(64-bit); /* public shift count */
            result[j]^=v&mask;
        }
    }
    memcpy(out,result,sizeof(result));cntru_secure_wipe(result,sizeof(result));
}
static void f2_square(uint64_t out[4],const uint64_t a[4]) {
    uint64_t result[4]={0};
    for(unsigned j=0;j<256;j++) {
        unsigned target=(2*j)&255;
        result[target>>6]^=((a[j>>6]>>(j&63))&1)<<(target&63);
    }
    memcpy(out,result,sizeof(result));cntru_secure_wipe(result,sizeof(result));
}
static uint32_t f2_unit(const int16_t f[512]) {
    uint32_t parity=0;
    for(unsigned j=0;j<512;j++)parity^=(uint32_t)(int32_t)f[j];
    return parity&1U;
}
static uint32_t f2_inverse(uint64_t out[4],const int16_t f[512]) {
    uint64_t a[4]={0},power[4];
    for(unsigned j=0;j<256;j++)a[j>>6]|=(uint64_t)((uint32_t)(f[j]+f[j+256])&1)<<(j&63);
    memcpy(out,a,sizeof(a));memcpy(power,a,sizeof(a));
    for(unsigned j=0;j<7;j++){f2_square(power,power);f2_multiply(out,out,power);}
    uint32_t valid=f2_unit(f);
    cntru_secure_wipe(a,sizeof(a));cntru_secure_wipe(power,sizeof(power));
    return valid;
}

static void sample_word(int16_t out[4],unsigned which,uint32_t x) {
    x&=word_mask[which];
    for(unsigned k=0;k<4;k++)out[k]=0;
    uint32_t lower=0;
    for(unsigned row=0;row<17;row++) {
        uint32_t upper=cdf[which][row];
        uint32_t select=(1U^ct_less_u32(x,lower))&ct_less_u32(x,upper);
        uint32_t mask=ct_mask_u32(select);
        for(unsigned k=0;k<4;k++)out[k]+=(int16_t)((int32_t)atoms[row][k]&(int32_t)mask);
        lower=upper;
    }
}
static void sample_from_bytes(int16_t out[512],unsigned which,const uint8_t bytes[256]) {
    for(unsigned j=0;j<128;j++) {
        int16_t block[4];sample_word(block,which,(uint32_t)bytes[2*j]|((uint32_t)bytes[2*j+1]<<8));
        for(unsigned k=0;k<4;k++)out[j+128*k]=block[k];
        cntru_secure_wipe(block,sizeof(block));
    }
}
int cntru_sample_poly(int16_t out[512],unsigned which,cntru_rng rng,void *ctx) {
    uint8_t bytes[256];
    if(which>2||!rng){memset(out,0,1024);return -1;}
    if(rng(ctx,bytes,sizeof(bytes))){cntru_secure_wipe(bytes,sizeof(bytes));memset(out,0,1024);return -1;}
    sample_from_bytes(out,which,bytes);cntru_secure_wipe(bytes,sizeof(bytes));return 0;
}
static void sample_rm_from_bytes(int16_t r[512],int16_t m[512],const uint8_t u[32],const uint8_t rho[384]) {
    sample_from_bytes(r,2,rho);
    unsigned cursor=0;
    for(unsigned j=0;j<128;j++) {
        uint32_t residue=((u[j>>3]>>(j&7))&1U)|(((u[16+(j>>3)]>>(j&7))&1U)<<1);
        uint32_t value=cntru_oblivious_byte(rho+256,128,cursor);
        cursor+=ct_nonzero_u32(residue);
        int16_t block[4]={0};
        for(unsigned row=0;row<16;row++) {
            const int8_t *candidate=lift_candidates[row];
            uint32_t selected=ct_equal_u32(residue,(uint32_t)candidate[0])
                &ct_equal_u32(value&(uint32_t)candidate[1],(uint32_t)candidate[2]);
            uint32_t mask=ct_mask_u32(selected);
            for(unsigned k=0;k<4;k++)block[k]+=(int16_t)((int32_t)candidate[3+k]&(int32_t)mask);
        }
        for(unsigned k=0;k<4;k++) {
            int sign=1-2*(int)(k&1);
            r[j+128*k]=(int16_t)(sign*r[j+128*k]);m[j+128*k]=(int16_t)(sign*block[k]);
        }
        cntru_secure_wipe(block,sizeof(block));
    }
}
int cntru_sample_rm(int16_t r[512],int16_t m[512],const uint8_t u[32],cntru_rng rng,void *ctx) {
    uint8_t rho[384];
    if(!rng||rng(ctx,rho,sizeof(rho))) {
        cntru_secure_wipe(rho,sizeof(rho));memset(r,0,1024);memset(m,0,1024);return -1;
    }
    sample_rm_from_bytes(r,m,u,rho);cntru_secure_wipe(rho,sizeof(rho));return 0;
}

int cntru_keygen(uint8_t pk[495],cntru_sk *sk,cntru_rng rng,void *ctx) {
    uint8_t fbytes[256*256]={0},gbytes[2*256]={0},z[32]={0};
    int16_t candidate[512],g[512]={0},fq[512],h[512];
    memset(sk,0,sizeof(*sk));memset(pk,0,495);
    if(!rng)rng=cntru_randombytes;
    unsigned source_error=0;
    source_error|=(unsigned)(rng(ctx,fbytes,sizeof(fbytes))!=0);
    source_error|=(unsigned)(rng(ctx,gbytes,sizeof(gbytes))!=0);
    source_error|=(unsigned)(rng(ctx,z,sizeof(z))!=0);
    if(source_error) {
        cntru_secure_wipe(fbytes,sizeof(fbytes));cntru_secure_wipe(gbytes,sizeof(gbytes));cntru_secure_wipe(z,sizeof(z));
        return -1;
    }
    uint32_t found_f=0,found_g=0;
    for(unsigned trial=0;trial<256;trial++) {
        sample_from_bytes(candidate,0,fbytes+256*trial);
        uint32_t unit=f2_unit(candidate);
        uint32_t mask=ct_mask_u32(unit&(1U^found_f));
        for(unsigned j=0;j<512;j++)
            sk->f[j]=(int16_t)(((uint32_t)(int32_t)sk->f[j]&~mask)|((uint32_t)(int32_t)candidate[j]&mask));
        found_f|=unit;
    }
    for(unsigned trial=0;trial<2;trial++) {
        sample_from_bytes(candidate,1,gbytes+256*trial);
        uint32_t nonzero=0;
        for(unsigned j=0;j<512;j++)nonzero|=(uint32_t)(int32_t)candidate[j];
        nonzero=ct_nonzero_u32(nonzero);
        uint32_t mask=ct_mask_u32(nonzero&(1U^found_g));
        for(unsigned j=0;j<512;j++)
            g[j]=(int16_t)(((uint32_t)(int32_t)g[j]&~mask)|((uint32_t)(int32_t)candidate[j]&mask));
        found_g|=nonzero;
    }
    /* In this fixed support every nonzero q-polynomial is a unit. Selecting
     * the first odd f therefore reproduces the original accepted distribution
     * conditioned on pool success. Independently check the norm arithmetic. */
    uint32_t valid=found_f&found_g;
    valid&=f2_inverse(sk->fp_inverse,sk->f);
    valid&=cntru_ct_poly_inverse_n(fq,sk->f,512);
    valid&=cntru_ct_poly_unit_n(g,512);
    cntru_poly_mul(h,g,fq);
    (void)cntru_pack(pk,h);
    memcpy(sk->h,h,sizeof(h));memcpy(sk->public_key,pk,495);memcpy(sk->rejection_seed,z,32);
    uint32_t success_mask=ct_mask_u32(valid);
    for(unsigned j=0;j<495;j++)pk[j]&=(uint8_t)success_mask;
    for(size_t j=0;j<sizeof(*sk);j++)((uint8_t*)sk)[j]&=(uint8_t)success_mask;
    cntru_secure_wipe(fbytes,sizeof(fbytes));cntru_secure_wipe(gbytes,sizeof(gbytes));cntru_secure_wipe(z,sizeof(z));
    cntru_secure_wipe(candidate,sizeof(candidate));cntru_secure_wipe(g,sizeof(g));cntru_secure_wipe(fq,sizeof(fq));cntru_secure_wipe(h,sizeof(h));
    return (int)valid-1;
}

/* h is validated public data. All output coefficients are canonical. */
static void encrypt_sampled(int16_t c[512],const int16_t h[512],
                            const int16_t r[512],const int16_t m[512]) {
    cntru_poly_mul(c,h,r);
    for(unsigned j=0;j<256;j++) {
        c[j]=ct_mod_q(c[j]+((211+1)/2)*(m[j]+m[j+256]));
        c[j+256]=ct_mod_q(c[j+256]+((211+1)/2)*(m[j+256]-m[j]));
    }
}
static int base_encrypt_with_h(uint8_t ct[495],const int16_t h[512],const uint8_t u[32],cntru_rng rng,void *ctx) {
    int16_t r[512],m[512],c[512];
    if(cntru_sample_rm(r,m,u,rng,ctx)) {
        memset(ct,0,495);cntru_secure_wipe(r,sizeof(r));cntru_secure_wipe(m,sizeof(m));return -1;
    }
    encrypt_sampled(c,h,r,m);
    (void)cntru_pack(ct,c);
    cntru_secure_wipe(r,sizeof(r));cntru_secure_wipe(m,sizeof(m));cntru_secure_wipe(c,sizeof(c));
    return 0;
}
int cntru_base_encrypt(uint8_t ct[495],const uint8_t pk[495],const uint8_t u[32],cntru_rng rng,void *ctx) {
    int16_t h[512];
    if(!rng)rng=cntru_randombytes;
    int status=cntru_unpack(h,pk); /* Parsing depends only on public input. */
    if(status){memset(ct,0,495);cntru_secure_wipe(h,sizeof(h));return -1;}
    status=base_encrypt_with_h(ct,h,u,rng,ctx);
    cntru_secure_wipe(h,sizeof(h));return status;
}
static int base_decrypt_with_c(uint8_t u[32],const cntru_sk *sk,const int16_t c[512],int status) {
    int16_t product[512];
    uint64_t residue[4]={0},bits[4];
    cntru_poly_mul(product,sk->f,c);
    for(unsigned j=0;j<256;j++) {
        uint32_t a=(uint32_t)ct_mod_q(product[j]-product[j+256]);
        uint32_t b=(uint32_t)ct_mod_q(product[j]+product[j+256]);
        int32_t ac=(int32_t)a-(int32_t)(211U*ct_less_u32(105,a));
        int32_t bc=(int32_t)b-(int32_t)(211U*ct_less_u32(105,b));
        residue[j>>6]|=(uint64_t)((uint32_t)(ac+bc)&1U)<<(j&63);
    }
    f2_multiply(bits,sk->fp_inverse,residue);
    uint32_t valid_mask=ct_mask_u32(1U^ct_nonzero_u32((uint32_t)status));
    for(unsigned j=0;j<32;j++)u[j]=(uint8_t)(bits[j>>3]>>((j&7)*8))&(uint8_t)valid_mask;
    cntru_secure_wipe(product,sizeof(product));cntru_secure_wipe(residue,sizeof(residue));cntru_secure_wipe(bits,sizeof(bits));
    return status;
}
int cntru_base_decrypt(uint8_t u[32],const cntru_sk *sk,const uint8_t ct[495]) {
    int16_t c[512];int status=cntru_unpack(c,ct);
    status=base_decrypt_with_c(u,sk,c,status);
    cntru_secure_wipe(c,sizeof(c));return status;
}

int cntru_encrypt(uint8_t ct[527],const uint8_t pk[495],const uint8_t message[32],cntru_rng rng,void *ctx) {
    uint8_t u[32]={0},mask[32];
    if(!rng)rng=cntru_randombytes;
    if(rng(ctx,u,32)||cntru_base_encrypt(ct,pk,u,rng,ctx)) {
        memset(ct,0,527);cntru_secure_wipe(u,sizeof(u));return -1;
    }
    mask_hash(mask,pk,u);
    for(unsigned j=0;j<32;j++)ct[495+j]=message[j]^mask[j];
    cntru_secure_wipe(u,sizeof(u));cntru_secure_wipe(mask,sizeof(mask));return 0;
}
int cntru_decrypt(uint8_t message[32],const cntru_sk *sk,const uint8_t *ct,size_t ct_len) {
    uint8_t u[32],mask[32];
    if(ct_len!=527){memset(message,0,32);return -1;}
    int status=cntru_base_decrypt(u,sk,ct);
    mask_hash(mask,sk->public_key,u);
    uint32_t valid_mask=ct_mask_u32(1U^ct_nonzero_u32((uint32_t)status));
    for(unsigned j=0;j<32;j++)message[j]=(ct[495+j]^mask[j])&(uint8_t)valid_mask;
    cntru_secure_wipe(u,sizeof(u));cntru_secure_wipe(mask,sizeof(mask));return status;
}
/* The deterministic tape is already available: use its exact fixed slices
 * directly, without a callback or a second serialization during FO checking. */
static void deterministic_polynomial(int16_t c[512],uint8_t masked[32],
        const uint8_t pk[495],const int16_t h[512],const uint8_t message[32]) {
    uint8_t coins[416],mask[32];int16_t r[512],m[512];shake_ctx ctx;
    hash_start(&ctx,'G',pk);absorb_part(&ctx,message,32);squeeze(&ctx,coins,sizeof(coins));
    sample_rm_from_bytes(r,m,coins,coins+32);
    encrypt_sampled(c,h,r,m);
    mask_hash(mask,pk,coins);
    for(unsigned j=0;j<32;j++)masked[j]=message[j]^mask[j];
    cntru_secure_wipe(coins,sizeof(coins));cntru_secure_wipe(mask,sizeof(mask));
    cntru_secure_wipe(r,sizeof(r));cntru_secure_wipe(m,sizeof(m));cntru_secure_wipe(&ctx,sizeof(ctx));
}
static int deterministic_encrypt_with_h(uint8_t ct[527],const uint8_t pk[495],const int16_t h[512],const uint8_t message[32]) {
    int16_t c[512];
    deterministic_polynomial(c,ct+495,pk,h,message);
    (void)cntru_pack(ct,c);
    cntru_secure_wipe(c,sizeof(c));return 0;
}
int cntru_deterministic_encrypt(uint8_t ct[527],const uint8_t pk[495],const uint8_t message[32]) {
    int16_t h[512];
    int status=cntru_unpack(h,pk);
    if(status){memset(ct,0,527);cntru_secure_wipe(h,sizeof(h));return -1;}
    status=deterministic_encrypt_with_h(ct,pk,h,message);
    cntru_secure_wipe(h,sizeof(h));return status;
}
int cntru_encaps(uint8_t ct[527],uint8_t key[32],const uint8_t pk[495],cntru_rng rng,void *ctx) {
    uint8_t message[32]={0};int16_t h[512];
    if(!rng)rng=cntru_randombytes;
    int invalid=cntru_unpack(h,pk);
    if(invalid||rng(ctx,message,32)||deterministic_encrypt_with_h(ct,pk,h,message)) {
        memset(ct,0,527);memset(key,0,32);cntru_secure_wipe(message,sizeof(message));cntru_secure_wipe(h,sizeof(h));return -1;
    }
    key_hash(key,pk,ct,527,message);cntru_secure_wipe(message,sizeof(message));cntru_secure_wipe(h,sizeof(h));return 0;
}
int cntru_decaps(uint8_t key[32],const cntru_sk *sk,const uint8_t *ct,size_t ct_len) {
    uint8_t padded[527]={0},u[32],mask[32],message[32],masked[32],selected[32];
    int16_t c[512],candidate[512];
    uint32_t length_valid=(uint32_t)(ct_len==527);
    if(ct_len==527)memcpy(padded,ct,527); /* public length only */
    int canonical=cntru_unpack(c,padded);
    (void)base_decrypt_with_c(u,sk,c,canonical);
    mask_hash(mask,sk->public_key,u);
    for(unsigned j=0;j<32;j++)message[j]=padded[495+j]^mask[j];
    deterministic_polynomial(candidate,masked,sk->public_key,sk->h,message);
    /* Canonical radix-q encoding is injective. With the explicit canonical
     * flag, equality of all coefficients and mask bytes is exactly equality
     * of the original serialized candidate, including invalid-core rejection. */
    uint32_t difference=0;
    for(unsigned j=0;j<512;j++)difference|=(uint32_t)(uint16_t)(candidate[j]^c[j]);
    for(unsigned j=0;j<32;j++)difference|=masked[j]^padded[495+j];
    uint32_t valid=length_valid&(1U^ct_nonzero_u32((uint32_t)canonical))
        &(1U^ct_nonzero_u32(difference));
    uint32_t valid_mask=ct_mask_u32(valid);
    for(unsigned j=0;j<32;j++)selected[j]=(message[j]&(uint8_t)valid_mask)|(sk->rejection_seed[j]&(uint8_t)~valid_mask);
    key_hash(key,sk->public_key,ct,ct_len,selected);
    cntru_secure_wipe(padded,sizeof(padded));cntru_secure_wipe(u,sizeof(u));cntru_secure_wipe(mask,sizeof(mask));
    cntru_secure_wipe(message,sizeof(message));cntru_secure_wipe(c,sizeof(c));cntru_secure_wipe(candidate,sizeof(candidate));
    cntru_secure_wipe(masked,sizeof(masked));cntru_secure_wipe(selected,sizeof(selected));return 0;
}
