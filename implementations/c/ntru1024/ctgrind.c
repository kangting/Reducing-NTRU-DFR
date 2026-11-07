/* Run the actual optimized binary under Valgrind Memcheck. Undefined bytes
 * stand for secrets; conditional jumps/addresses depending on them are errors.
 * Explicit API status and public ciphertext releases are declassified only
 * AFTER the call. This is a dynamic test, not a constant-time proof. */
#include "cntru.h"
#include <stdio.h>
#include <string.h>
#include <valgrind/memcheck.h>

typedef struct {uint8_t bytes[262144];size_t cursor;} tape;
static int secret_rng(void *opaque,uint8_t *out,size_t length) {
    tape *t=opaque;
    if(length>sizeof(t->bytes)-t->cursor)return -1;
    memcpy(out,t->bytes+t->cursor,length);t->cursor+=length;
    VALGRIND_MAKE_MEM_UNDEFINED(out,length);
    return 0;
}
static void release(void *v,size_t n){VALGRIND_MAKE_MEM_DEFINED(v,n);}
int main(void) {
    tape t;t.cursor=0;
    cntru_shake256(t.bytes,sizeof(t.bytes),(const uint8_t*)"hardened taint tests",20);
    uint8_t pk[CNTRU_PK_BYTES],ct[CNTRU_CT_BYTES],key[32],recovered[32],u[CNTRU_U_BYTES],packed[CNTRU_PK_BYTES];
    int16_t a[CNTRU_N],b[CNTRU_N],c[CNTRU_N];cntru_sk sk;
    int status=cntru_keygen(pk,&sk,secret_rng,&t);
    release(&status,sizeof(status));release(pk,sizeof(pk));release(sk.public_key,sizeof(sk.public_key));release(sk.h,sizeof(sk.h));
    if(status)return 1;
    status=cntru_encaps(ct,key,pk,secret_rng,&t);
    release(&status,sizeof(status));release(ct,sizeof(ct));
    if(status)return 1;
    (void)cntru_decaps(recovered,&sk,ct,sizeof(ct));
    ct[0]^=1;(void)cntru_decaps(recovered,&sk,ct,sizeof(ct));
    memset(ct,255,sizeof(ct));(void)cntru_decaps(recovered,&sk,ct,sizeof(ct));
    (void)cntru_decaps(recovered,&sk,NULL,0);
    for(unsigned j=0;j<CNTRU_N;j++){a[j]=(int16_t)(j%CNTRU_Q);b[j]=(int16_t)((int)(j%(2*CNTRU_Q-1))-(CNTRU_Q-1));}
    VALGRIND_MAKE_MEM_UNDEFINED(a,sizeof(a));VALGRIND_MAKE_MEM_UNDEFINED(b,sizeof(b));
    cntru_poly_mul(c,a,b);cntru_poly_mul(c,a,a);
    (void)cntru_poly_inv(c,sk.f);
    (void)cntru_pack(packed,a);(void)cntru_unpack(c,packed);
    for(unsigned pattern=0;pattern<3;pattern++) {
        memset(u,pattern==0?0:pattern==1?255:0x55,sizeof(u));
        VALGRIND_MAKE_MEM_UNDEFINED(u,sizeof(u));
        status=cntru_sample_rm(a,b,u,secret_rng,&t);
        release(&status,sizeof(status));if(status)return 1;
        status=cntru_deterministic_encrypt(ct,pk,u);
        release(&status,sizeof(status));if(status)return 1;
    }
    puts("PASS: secret-taint paths executed; require Valgrind ERROR SUMMARY:0 and exit0");
    return 0;
}
