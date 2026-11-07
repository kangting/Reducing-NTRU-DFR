#include "ct_radix.h"
#include "ct_radix_generated.h"
#include <stdio.h>
#include <valgrind/memcheck.h>

static void check(const ct_radix_plan *p) {
    int16_t a[CT_RADIX_MAX_N];
    uint8_t encoded[CT_RADIX_MAX_LIMBS*8];
    for(unsigned i=0;i<p->n;i++)a[i]=(int16_t)(i%p->q);
    VALGRIND_MAKE_MEM_UNDEFINED(a,p->n*sizeof(*a));
    int status=ct_radix_pack(encoded,a,p);
    VALGRIND_MAKE_MEM_DEFINED(&status,sizeof(status));
    VALGRIND_MAKE_MEM_DEFINED(encoded,p->encoded_bytes);
    VALGRIND_MAKE_MEM_DEFINED(a,p->n*sizeof(*a));
    VALGRIND_MAKE_MEM_UNDEFINED(encoded,p->encoded_bytes);
    status=ct_radix_unpack(a,encoded,p);
    VALGRIND_MAKE_MEM_DEFINED(&status,sizeof(status));
    VALGRIND_MAKE_MEM_DEFINED(encoded,p->encoded_bytes);
    VALGRIND_MAKE_MEM_DEFINED(a,p->n*sizeof(*a));
    for(unsigned i=0;i<p->n;i++)a[i]=-1;
    VALGRIND_MAKE_MEM_UNDEFINED(a,p->n*sizeof(*a));
    status=ct_radix_pack(encoded,a,p);
    VALGRIND_MAKE_MEM_DEFINED(&status,sizeof(status));
    VALGRIND_MAKE_MEM_DEFINED(encoded,p->encoded_bytes);
    VALGRIND_MAKE_MEM_DEFINED(a,p->n*sizeof(*a));
    for(unsigned i=0;i<p->encoded_bytes;i++)encoded[i]=255;
    VALGRIND_MAKE_MEM_UNDEFINED(encoded,p->encoded_bytes);
    status=ct_radix_unpack(a,encoded,p);
    VALGRIND_MAKE_MEM_DEFINED(&status,sizeof(status));
    VALGRIND_MAKE_MEM_DEFINED(encoded,p->encoded_bytes);
    VALGRIND_MAKE_MEM_DEFINED(a,p->n*sizeof(*a));
}
int main(void) {
    check(&ct_radix_n512_q211);check(&ct_radix_n1024_q307);
    check(&ct_radix_n1024_q331);check(&ct_radix_n1024_q373);
    puts("ct_radix taint paths completed");return 0;
}
