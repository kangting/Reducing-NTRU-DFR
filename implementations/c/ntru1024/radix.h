#ifndef CNTRU_RADIX_LOCAL_H
#define CNTRU_RADIX_LOCAL_H
#include "config.h"
#define CT_RADIX_PREFIX CNTRU_NAMESPACE(common_)
#define CT_RADIX_STATIC_PLANS_ONLY
#include "../common/ct_radix_generated.h"
#if CNTRU_Q == 307
#define CNTRU_RADIX_PLAN ct_radix_n1024_q307
#elif CNTRU_Q == 331
#define CNTRU_RADIX_PLAN ct_radix_n1024_q331
#elif CNTRU_Q == 373
#define CNTRU_RADIX_PLAN ct_radix_n1024_q373
#endif
#endif
