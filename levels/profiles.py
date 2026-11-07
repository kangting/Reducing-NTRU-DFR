"""Exact n=1024 comparison profiles transcribed from the user's specification.

Security/DFR estimates are attributed inputs, not independently certified costs.
The canonical wire contract has its own fingerprint and domain identifier.
"""
from __future__ import annotations
import argparse
from fractions import Fraction
import hashlib
import json
from math import isqrt
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
VERSION = 'Complementary-NTRU-ACWC0-FO-levels-v1'
MASSES = {
    307: [(4, 3, 1, 8)]*3,
    331: [(32, 16, 16, 64), (32, 16, 16, 64), (32, 19, 13, 64)],
    373: [(110, 34, 112, 256), (128, 14, 114, 256), (128, 31, 97, 256)],
}
ESTIMATES = {
    307: dict(label='Level III comparison candidate', classical=250.67, quantum=234.14, dfr_upper_bound_exponent=176.95),
    331: dict(label='Kyber-1024 classical-cost comparison candidate', classical=262.28, quantum=244.59, dfr_upper_bound_exponent=176.05),
    373: dict(label='DAWN classical/quantum Level V comparison candidate', classical=270.05, quantum=251.57, dfr_upper_bound_exponent=177.72),
}


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode('ascii')


def verify_contract_math(profile):
    """Check the support/unit theorem hypotheses, without changing wire bytes.

    For y=x^256, y^4+1=0 and y has order 8. The two multiplicative
    orders below give [F_q(x):F_q(y)]=512/2=256 at every root of x^1024+1.
    Thus the 256 block positions are independent over F_q(y). Each nonzero
    supported block is a unit modulo y^4+1, so a supported polynomial is
    a q-unit exactly when it is nonzero. Odd f is also an F_2-unit.
    """
    q = profile['q']
    if q < 3 or any(q % d == 0 for d in range(2, isqrt(q)+1)):
        raise ValueError('q must be prime')
    if pow(q, 512, 2048) != 1 or pow(q, 256, 2048) == 1:
        raise ValueError('Expected order 512 modulo 2048')
    if pow(q, 2, 8) != 1 or q % 8 == 1:
        raise ValueError('Expected order 2 modulo 8')
    support = {(0, 0, 0, 0)}
    for j in range(4):
        mono = [0]*4; mono[j] = 1
        pair = mono.copy(); pair[(j+1) % 4] = -1 if j == 3 else 1
        for atom in (mono, pair):
            support.add(tuple(atom)); support.add(tuple(-v for v in atom))
    atoms = [tuple(row['atom']) for row in profile['tables'][0]['rows']]
    if atoms != sorted(support):
        raise ValueError('Expected the exact ordered negacyclic 17-atom support')

    def trim(poly):
        while poly and poly[-1] == 0: poly.pop()
        return poly

    def remainder(a, b):
        a = trim([v % q for v in a])
        while len(a) >= len(b):
            factor = a[-1]*pow(b[-1], -1, q) % q
            offset = len(a)-len(b)
            for i, value in enumerate(b): a[i+offset] = (a[i+offset]-factor*value) % q
            trim(a)
        return a

    for atom in support-{(0, 0, 0, 0)}:
        a, b = [1, 0, 0, 0, 1], trim([v % q for v in atom])
        while b: a, b = b, remainder(a, b)
        if len(a) != 1: raise ValueError('Nonzero block is not a unit modulo y^4+1')
    for table in profile['tables']:
        if [tuple(row['atom']) for row in table['rows']] != atoms:
            raise ValueError('Inconsistent support across distributions')
    f_mass, g_mass = (profile['orbit_masses'][name] for name in ('f', 'g'))
    if Fraction(g_mass[0], g_mass[3]) != Fraction(1, 2):
        raise ValueError('The two-g-candidate failure bound assumes zero mass 1/2')
    odd_block = Fraction(f_mass[1], f_mass[3])
    # P(no odd f among 256 candidates) = 2^-256 * (1+(1-2p)^256)^256.
    if (1+(1-2*odd_block)**256)**256 >= 2:
        raise ValueError('The fixed f pool does not meet the strict 2^-255 bound')


def make_profile(q):
    original = json.loads((REPO/'ntru/par.json').read_text())
    atoms = [row['atom'] for row in original['tables'][0]['rows']]
    if len(atoms) != 17 or len({tuple(a) for a in atoms}) != 17:
        raise ValueError('Original atom order is not the expected 17-element support')
    counts = [sum(sum(v != 0 for v in atom) == k for atom in atoms) for k in range(3)]
    if counts != [1, 8, 8]: raise ValueError('Unexpected orbit sizes')
    tables = []
    for name, mass in zip(('f', 'g', 'r', 'm'), [*MASSES[q], (1, 2, 1, 4)]):
        z, monomial, pair, denominator = mass
        if z+monomial+pair != denominator: raise ValueError('Orbit masses do not sum to one')
        rows = []
        for atom in atoms:
            orbit = sum(v != 0 for v in atom)
            probability = Fraction((z, monomial, pair)[orbit], denominator*counts[orbit])
            rows.append(dict(atom=atom, numerator=probability.numerator, denominator=probability.denominator))
        if sum(Fraction(row['numerator'], row['denominator']) for row in rows) != 1:
            raise ValueError('Invalid probability normalization')
        tables.append(dict(name=name, rows=rows))
    n = 1024
    core = ((q**n-1).bit_length()+7)//8
    contract = dict(n=n, q=q, ring='Z_q[x]/(x^1024+1)', p_exponent=512,
                    block_offsets=[0, 256, 512, 768], key_signs=[1, 1, 1, 1],
                    ciphertext_signs=[1, -1, 1, -1],
                    internal_residue_bytes=64, external_message_bytes=32,
                    shared_key_bytes=32, rejection_seed_bytes=32,
                    pk_bytes=core, core_bytes=core, ct_bytes=core+32,
                    f_candidates=256, g_candidates=2, keygen_rng_requests=[131072, 1024, 32],
                    fgr_word_bytes=2, fgr_mapping='LE16 & (LCM/GCD-normalized CDF total - 1)',
                    message_mapping='compact-prefix conditional bytes: classes 0/1/2/3 use no byte/&3/&3/&7',
                    rho_bytes=768, g_output_bytes=832, f_output_bytes=32, h_output_bytes=32,
                    encoding='canonical little-endian radix-q; reject integers >= q^1024',
                    framing='ordered byte tuples, each prefixed by uint64 little-endian length',
                    version=VERSION, tables=tables)
    fingerprint = hashlib.sha256(canonical_bytes(contract)).hexdigest()
    profile = {**contract, 'wire_contract_sha256': fingerprint,
               'parameter_id': f'n1024-q{q}-P1+x512-block17-{fingerprint}',
               'orbit_masses': {name: list(mass) for name, mass in zip(('f', 'g', 'r', 'm'), [*MASSES[q], (1, 2, 1, 4)])},
               'user_supplied_estimates': {**ESTIMATES[q],
                   'scope': 'Selected structured GSA paths with MATZOV costing; average accepted-key internal DFR upper bound.',
                   'independently_reproduced_here': False,
                   'not_claimed': ['NIST certification', 'complete DAWN attack enumeration', 'global parameter optimality']}}
    verify_contract_math(profile)
    return profile


def load_profile(q):
    if q not in MASSES: raise ValueError('Unsupported profile')
    profile = json.loads((HERE/'params'/f'q{q}.json').read_text())
    if profile != make_profile(q):
        raise ValueError('Frozen parameter file differs from the explicit profile specification')
    return profile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    (HERE/'params').mkdir(parents=True, exist_ok=True)
    for q in MASSES:
        profile = make_profile(q)
        path = HERE/'params'/f'q{q}.json'
        if args.check:
            load_profile(q)
        elif path.exists():
            if json.loads(path.read_text()) != profile: raise ValueError('Refusing to overwrite a different frozen profile')
        else:
            path.write_text(json.dumps(profile, indent=2)+'\n')
        print(json.dumps({key: profile[key] for key in ('q', 'parameter_id', 'pk_bytes', 'ct_bytes')}))


if __name__ == '__main__': main()
