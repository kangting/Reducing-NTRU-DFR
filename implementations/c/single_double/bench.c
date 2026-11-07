/* PMU cycle driver for the selected family. */
#include "../../../benchmarks/include/driver.h"
#include "src/cntru.h"
static cntru_sk sk[KEYS],scratch_sk;
static uint8_t pk[KEYS][CNTRU_PK_BYTES],scratch_pk[CNTRU_PK_BYTES];
static uint8_t ct[POOL][CNTRU_CT_BYTES],shared[POOL][CNTRU_KEY_BYTES],scratch_ct[CNTRU_CT_BYTES],scratch_key[CNTRU_KEY_BYTES];
static int message_rng(void *opaque,uint8_t *out,size_t count){if(count!=CNTRU_MESSAGE_BYTES)return -1;memcpy(out,opaque,count);return 0;}
static void backend_init(void) {
    for(unsigned i=0;i<KEYS;i++)need(cntru_keygen(pk[i],&sk[i],os_random,NULL)==0,"family keygen setup");
    for(unsigned i=0;i<POOL;i++)need(cntru_encaps(ct[i],shared[i],pk[i%KEYS],message_rng,messages[i])==0,"family encaps setup");
}
static void backend_keygen(void){need(cntru_keygen(scratch_pk,&scratch_sk,os_random,NULL)==0,"family keygen");observe(scratch_pk,sizeof(scratch_pk));observe(&scratch_sk,sizeof(scratch_sk));}
static void backend_encaps(unsigned i){need(cntru_encaps(scratch_ct,scratch_key,pk[i%KEYS],message_rng,messages[i])==0,"family encaps");observe(scratch_ct,sizeof(scratch_ct));observe(scratch_key,sizeof(scratch_key));}
static void backend_decaps(unsigned i){need(cntru_decaps(scratch_key,&sk[i%KEYS],ct[i],sizeof(ct[i]))==0,"family decaps");observe(scratch_key,sizeof(scratch_key));}
static void backend_check(void){for(unsigned i=0;i<POOL;i++){backend_decaps(i);need(!memcmp(scratch_key,shared[i],sizeof(scratch_key)),"family shared key");backend_encaps(i);need(!memcmp(scratch_ct,ct[i],sizeof(scratch_ct)),"family deterministic ciphertext");}}
int main(int argc,char **argv){return bench_main(argc,argv,CNTRU_PROFILE_ID,CNTRU_PK_BYTES,CNTRU_CT_BYTES,CNTRU_MESSAGE_BYTES);}
