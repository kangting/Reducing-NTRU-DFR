#ifndef CNTRU_LEVELS_CT_NTT_H
#define CNTRU_LEVELS_CT_NTT_H
#include <stdint.h>
#include "config.h"
void cntru_ct_poly_mul_n(int16_t *out,const int16_t *a,const int16_t *b,unsigned n);
#ifdef CNTRU_AVX2_NTT
void cntru_ct_poly_mul_avx2(int16_t *out,const int16_t *a,const int16_t *b,unsigned n);
#endif
uint32_t cntru_ct_poly_inverse_n(int16_t *out,const int16_t *a,unsigned n);
uint32_t cntru_ct_poly_unit_n(const int16_t *a,unsigned n);
#endif
