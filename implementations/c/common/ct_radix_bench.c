#define _GNU_SOURCE
#include "ct_radix.h"
#include "ct_radix_generated.h"
#include <dlfcn.h>
#include <inttypes.h>
#include <sched.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <x86intrin.h>

typedef int (*old_pack_fn)(uint8_t*,const int16_t*);
typedef int (*old_unpack_fn)(int16_t*,const uint8_t*);
static int16_t coefficients[256][CT_RADIX_MAX_N];
static uint8_t encodings[256][CT_RADIX_MAX_LIMBS*8];
static volatile unsigned sink;
static uint64_t state=UINT64_C(0x16a93ed507b42c8f);
static uint64_t random_word(void) {
    state^=state<<13;state^=state>>7;state^=state<<17;return state;
}
static uint64_t ticks(unsigned *aux) {
    _mm_lfence();uint64_t value=__rdtscp(aux);_mm_lfence();return value;
}
static uint64_t nanos(void) {
    struct timespec t;
    if(clock_gettime(CLOCK_MONOTONIC_RAW,&t))abort();
    return (uint64_t)t.tv_sec*UINT64_C(1000000000)+(uint64_t)t.tv_nsec;
}
static void run(const ct_radix_plan *p,const char *path,const char *prefix,unsigned count) {
    void *handle=dlopen(path,RTLD_NOW|RTLD_LOCAL);
    if(!handle) { fprintf(stderr,"%s\n",dlerror());exit(1); }
    char symbol[128];snprintf(symbol,sizeof(symbol),"%s_pack",prefix);
    old_pack_fn old_pack=(old_pack_fn)dlsym(handle,symbol);
    snprintf(symbol,sizeof(symbol),"%s_unpack",prefix);
    old_unpack_fn old_unpack=(old_unpack_fn)dlsym(handle,symbol);
    if(!old_pack || !old_unpack)abort();
    for(unsigned i=0;i<256;i++) {
        for(unsigned j=0;j<p->n;j++)coefficients[i][j]=(int16_t)(random_word()%p->q);
        if(ct_radix_pack(encodings[i],coefficients[i],p))abort();
    }
    int16_t output[CT_RADIX_MAX_N]={0};uint8_t encoded[CT_RADIX_MAX_LIMBS*8]={0};
    /* Identical pool and schedule; alternate old/new order every round. */
    for(unsigned round=0;round<9;round++)for(unsigned k=0;k<4;k++) {
        unsigned operation=k^((round&1)?1:0),aux0,aux1;
        uint64_t ns0=nanos(),t0=ticks(&aux0);
        unsigned status=0;
        for(unsigned i=0;i<count;i++) {
            unsigned index=(i*73U+19U)&255U;
            switch(operation) {
            case 0: status|=(unsigned)old_pack(encoded,coefficients[index]);break;
            case 1: status|=(unsigned)ct_radix_pack(encoded,coefficients[index],p);break;
            case 2: status|=(unsigned)old_unpack(output,encodings[index]);break;
            default:status|=(unsigned)ct_radix_unpack(output,encodings[index],p);break;
            }
        }
        uint64_t t1=ticks(&aux1),ns1=nanos();
        if(aux0!=aux1 || status)abort();
        sink^=encoded[0]^(unsigned)(uint16_t)output[0];
        printf("%u,%u,%u,%u,%u,%" PRIu64 ",%" PRIu64 ",%u\n",
               p->n,p->q,round,operation,count,t1-t0,ns1-ns0,aux0);
    }
    dlclose(handle);
}
int main(int argc,char **argv) {
    if(argc!=3) { fprintf(stderr,"usage: %s REPO ITERATIONS\n",argv[0]);return 1; }
    cpu_set_t cpus;CPU_ZERO(&cpus);CPU_SET(4,&cpus);
    if(sched_setaffinity(0,sizeof(cpus),&cpus)) { perror("affinity");return 1; }
    unsigned count=(unsigned)strtoul(argv[2],NULL,10);
    const ct_radix_plan *plans[]={&ct_radix_n512_q211,&ct_radix_n1024_q307,
                                &ct_radix_n1024_q331,&ct_radix_n1024_q373};
    puts("n,q,round,operation,iterations,tsc_ticks,elapsed_ns,tsc_aux");
    for(unsigned i=0;i<4;i++) {
        char path[4096],prefix[128];
        if(i==0) {
            snprintf(path,sizeof(path),"%s/benchmarks/build/q211-ref/libcntru.so",argv[1]);
            snprintf(prefix,sizeof(prefix),"cntru");
        } else {
            snprintf(path,sizeof(path),"%s/benchmarks/build/q%u-ref/libcntru.so",argv[1],plans[i]->q);
            snprintf(prefix,sizeof(prefix),"cntru1024q%u",plans[i]->q);
        }
        run(plans[i],path,prefix,count);
    }
    return sink==UINT32_MAX;
}
