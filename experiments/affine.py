"""Conditional normalized-key GSA estimate, derived from ntru/par.json.

This script evaluates moments and a length criterion. It does not construct
or reduce a lattice basis or measure key-recovery success.
"""
import argparse
from fractions import Fraction
from itertools import permutations
import json
from math import e, exp, log, pi, prod, sqrt
from pathlib import Path


ZERO = (0, 0, 0, 0)
MONOMIALS = tuple(tuple(sign if j == i else 0 for j in range(4))
                  for i in range(4) for sign in (-1, 1))


def times_y(atom):
    """Multiply a block by y in Z[y]/(y^4+1)."""
    return (-atom[3], atom[0], atom[1], atom[2])


def covariance(law):
    mean = [sum(p * a[i] for a, p in law.items()) for i in range(4)]
    return [[sum(p * (a[i] - mean[i]) * (a[j] - mean[j])
                 for a, p in law.items()) for j in range(4)] for i in range(4)]


def determinant(matrix):
    total = Fraction(0)
    for perm in permutations(range(4)):
        inversions = sum(perm[i] > perm[j] for i in range(4) for j in range(i + 1, 4))
        total += (-1)**inversions * prod(matrix[i][perm[i]] for i in range(4))
    return total


def model(data):
    if (data['n'], data['q']) != (512, 211):
        raise ValueError('this acceptance analysis is for n=512, q=211')
    laws = {}
    for table in data['tables']:
        law = {tuple(row['atom']): Fraction(row['numerator'], row['denominator'])
               for row in table['rows']}
        if len(law) != len(table['rows']) or sum(law.values()) != 1:
            raise ValueError('invalid probability table')
        if any(len(a) != 4 or p <= 0 for a, p in law.items()):
            raise ValueError('expected positive four-coefficient block probabilities')
        laws[table['name']] = law
    f, g = laws['f'], laws['g']
    # Invariance under y also gives invariance under -1 since y^4=-1.
    # Combined with independent identically distributed blocks, this makes
    # simultaneous division by any signed x-monomial distribution-preserving.
    for law in (f, g):
        if any(law.get(times_y(a)) != p for a, p in law.items()):
            raise ValueError('normalization requires signed-rotation invariant laws')
    image = {tuple(a[i] + times_y(a)[i] for i in range(4)): a
             for a in (ZERO,) + MONOMIALS}
    if set(f) != set(image) | set(MONOMIALS) or set(g) != set(f):
        raise ValueError('expected zero, signed monomials and signed adjacent pairs')
    odd = sum(p for a, p in f.items() if sum(a) % 2)
    a_law = {preimage: f[atom] / (1 - odd) for atom, preimage in image.items()}
    blocks = data['n'] // 4
    accepted_f = (1 - (1 - 2 * odd)**blocks) / 2
    subset = blocks * odd * (1 - odd)**(blocks - 1) / accepted_f
    a_cov, g_cov = covariance(a_law), covariance(g)
    a_var = a_cov[0][0]
    if a_cov != [[a_var if i == j else 0 for j in range(4)] for i in range(4)]:
        raise ValueError('conditional a law must have isotropic covariance')
    g_zero = g[ZERO]**blocks
    # Nonzero conditioning scales the whole covariance. The correction for
    # the published parameters is below binary64 resolution.
    b = float(determinant(g_cov))**0.25 / float(1 - g_zero)
    if a_var <= 0 or b <= 0:
        raise ValueError('nonpositive target width')
    return dict(n=data['n'], q=data['q'], first_dim=data['n'] - 4,
                odd=odd, accepted_f=accepted_f, subset=subset,
                a_law=a_law, a_var=a_var, g_cov=g_cov,
                g_zero=g_zero, b=b, xi=sqrt(b / float(a_var)))


def best_at(beta, values):
    shape = log(1.01295) if beta == 40 else (
        log(beta / (2 * pi * e)) + log(pi * beta) / beta) / (2 * (beta - 1))
    best = None
    for keep in range(4, values['n'] + 1, 4):
        dim = values['first_dim'] + keep + 1
        if dim < beta:
            continue
        logdet = (keep * log(values['q']) + values['first_dim'] * log(values['xi'])
                  + log(values['b']) / 2)
        margin = ((2 * beta - dim - 1) * shape + logdet / dim
                  - log(beta * values['b']) / 2)
        row = (margin, dim, keep, logdet)
        if best is None or row > best:
            best = row
    if best is None:
        return None
    margin, dim, keep, logdet = best
    return dict(beta=beta, dimension=dim, retained_second_coordinates=keep,
                log_margin=margin, criterion_ratio=exp(margin),
                log2_determinant=logdet / log(2))


def evaluate(data):
    values = model(data)
    for beta in range(40, values['first_dim'] + values['n'] + 2):
        result = best_at(beta, values)
        if result is not None and result['log_margin'] >= 0:
            break
    else:
        raise RuntimeError('no qualifying block size')
    result.update(classical_leading_sieve_exponent=0.292 * beta,
                  quantum_leading_sieve_exponent=0.257 * beta)
    return {
        'status': 'conditional GSA estimate; no basis reduction or recovery run',
        'parameter_source': 'ntru/par.json',
        'parameters': {key: values[key] for key in ('n', 'q', 'first_dim')},
        'subset': {
            'definition': 'exactly one odd-parity f block among accepted keys',
            'per_block_odd_probability': str(values['odd']),
            'f_acceptance_probability': float(values['accepted_f']),
            'accepted_key_probability': float(values['subset']),
            'g_nonzero_condition_cancels': True,
        },
        'conditional_a_law': {
            'known_zero_block': 0, 'independent_other_blocks': values['n'] // 4 - 1,
            'rows': [{'atom': list(a), 'probability': str(p)}
                     for a, p in sorted(values['a_law'].items())],
            'coefficient_variance': str(values['a_var']),
        },
        'second_moments': {
            'g_covariance_before_acceptance': [[str(v) for v in row] for row in values['g_cov']],
            'g_effective_variance': values['b'],
            'g_all_zero_probability': float(values['g_zero']),
            'g_nonzero_covariance_factor': '1/(1-P[g=0]); below binary64 resolution here',
            'scale_first_component': values['xi'],
            'embedding_height': sqrt(values['b']),
        },
        'lattice': {
            'relation': 'gbar = h + (1+y)*h*a (mod q); block 0 of a is zero',
            'dimension': '508+s+1',
            'determinant': 'q^s * xi^508 * sqrt(b)',
            'criterion': 'delta_beta^(2*beta-d-1)*D^(1/d) >= sqrt(beta*b)',
            'projection': 'complete four-coefficient blocks after determinant-one whitening',
            'normalization_guess_factor': 1,
        },
        'result': result,
        'previous_beta': best_at(beta - 1, values),
        'interpretation': [
            'The subset fraction is not a measured key-recovery success rate.',
            'With conditional recovery success s_rec, whole-key-distribution success contribution is p1*s_rec.',
            'Retrying a fixed target does not change its membership in the subset.',
            'The exponents count leading sieve work, not concrete gate counts or a Category 1 certification.',
            'The quantum exponent uses the manuscript quantum-random-access-memory model.',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, help='write the complete result as JSON')
    args = parser.parse_args()
    params = Path(__file__).resolve().parents[1] / 'ntru' / 'par.json'
    output = evaluate(json.loads(params.read_text()))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'subset_probability': output['subset']['accepted_key_probability'],
                      'result': output['result']}, indent=2))


if __name__ == '__main__':
    main()
