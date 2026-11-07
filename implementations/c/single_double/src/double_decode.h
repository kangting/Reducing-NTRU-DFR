#ifndef CNTRU_FAMILY_DOUBLE_DECODE_H
#define CNTRU_FAMILY_DOUBLE_DECODE_H
#include <stdint.h>
#include "config.h"

#define cntru_double_residue CNTRU_NAMESPACE(double_residue)

/* D-layer correction before multiplication by the F2 inverse.
 *
 * L=CNTRU_BLOCKS=N/4. The syndrome bit for group i is the XOR of the
 * parities at i, i+L, i+2L, i+3L. If precisely one group has syndrome1,
 * flip the parity at its largest absolute centered coefficient, selecting
 * the FIRST position i+kL (smallest k) in a tie. Zero syndrome flips none.
 * Fold the resulting parity modulo x^(N/2)+1 into little-endian uint64 bits.
 * Return1 iff at most one syndrome group was set; otherwise return0 and
 * output the original, uncorrected folded parity. Callers must propagate
 * the returned validity bit and perform the later F2-inverse/equal-halves
 * check; this helper is not the complete D decoder.
 *
 * All int16_t inputs, including -32768, are arithmetically supported.
 * Input/output must not overlap. Loop bounds and addresses depend only on
 * public configuration/indexes. Compiler/target CT validation is separate;
 * this source has not been executed under the current no-run instruction.
 */
uint32_t cntru_double_residue(uint64_t out[CNTRU_U_WORDS],
                              const int16_t centered[CNTRU_N]);
#endif
