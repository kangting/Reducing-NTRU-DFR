#define _POSIX_C_SOURCE 200809L
#include "cntru.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static double now(void) {
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC,&t)) abort();
    return (double)t.tv_sec*1e9+t.tv_nsec;
}
static int compare(const void *a,const void *b) {
    double x=*(const double*)a,y=*(const double*)b;
    return (x>y)-(x<y);
}
static volatile unsigned checksum;
#define MEASURE(label, code) do { \
    double batches[5]; \
    for(unsigned round=0;round<5;round++) { \
        double start=now(); \
        for(unsigned iteration=0;iteration<loops;iteration++) { \
            code; \
            __asm__ volatile("" : : : "memory"); \
        } \
        batches[round]=(now()-start)/loops; \
    } \
    qsort(batches,5,sizeof(double),compare); \
    printf("%s%.3f",label,batches[2]); \
} while(0)

int main(int argc,char **argv) {
    unsigned loops=argc>1?(unsigned)strtoul(argv[1],NULL,10):2000;
    if(!loops)return 1;
    uint8_t input[1200],out[416],pk[495],encoded[495];
    int16_t a[512],b[512],c[512];
    for(unsigned j=0;j<sizeof(input);j++)input[j]=(uint8_t)(17*j+31);
    for(unsigned j=0;j<512;j++){a[j]=(int16_t)((17*j+31)%211);b[j]=(int16_t)((j%3)-1);}
    if(cntru_pack(encoded,a))return 1;
    memcpy(pk,encoded,495);
    printf("{\"loops\":%u,\"rounds\":5,\"statistic\":\"median_batch_mean_ns\"",loops);
    MEASURE(",\"pack_ns\":",{if(cntru_pack(encoded,a))abort();checksum+=encoded[iteration%495];});
    MEASURE(",\"unpack_ns\":",{if(cntru_unpack(c,encoded))abort();checksum+=(unsigned)c[iteration%512];});
    MEASURE(",\"poly_mul_ns\":",{cntru_poly_mul(c,a,b);checksum+=(unsigned)c[iteration%512];});
    MEASURE(",\"shake_692_to32_ns\":",{cntru_shake256(out,32,input,692);checksum+=out[iteration%32];});
    MEASURE(",\"shake_660_to416_ns\":",{cntru_shake256(out,416,input,660);checksum+=out[iteration%416];});
    MEASURE(",\"deterministic_encrypt_ns\":",{uint8_t ct[527];if(cntru_deterministic_encrypt(ct,pk,input))abort();checksum+=ct[iteration%527];});
    printf(",\"checksum\":%u}\n",checksum);
    return 0;
}
