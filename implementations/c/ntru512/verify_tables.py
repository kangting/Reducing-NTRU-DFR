#!/usr/bin/env python3
"""Fail closed unless the frozen JSON law and all compiled public tables match."""
import argparse
import ast
from fractions import Fraction
from functools import reduce
import hashlib
import json
from math import gcd, lcm
from pathlib import Path
import re

EXPECTED_CONFIG_SHA256='1d05abcbcce101b10266bd6a5333fcaf89d9bb534e36b757f2e73c40fedfb5f1'


def require(condition,message):
    if not condition:
        raise ValueError(message)


def distribution(rows):
    probabilities=[Fraction(r['numerator'],r['denominator']) for r in rows]
    require(all(p>0 for p in probabilities),'nonpositive probability')
    denominator=lcm(*(p.denominator for p in probabilities))
    weights=[p.numerator*(denominator//p.denominator) for p in probabilities]
    divisor=reduce(gcd,weights)
    weights=[w//divisor for w in weights]
    cdf=[]
    total=0
    for w in weights:
        total+=w
        cdf.append(total)
    return probabilities,cdf,total


def expected_tables(root):
    data=json.loads((root.parents[2]/'implementations/python/ntru/par.json').read_text())
    encoded=json.dumps(data,sort_keys=True,separators=(',',':')).encode()
    require(hashlib.sha256(encoded).hexdigest()==EXPECTED_CONFIG_SHA256,
            'parameter law differs from the frozen version; review/version the backend before changing it')
    require((data['n'],data['q'])==(512,211),'unsupported ring')
    allowed={(0,0,0,0)}
    for position in range(4):
        monomial=[0]*4
        monomial[position]=1
        pair=monomial.copy()
        pair[(position+1)%4]+=1 if position<3 else -1
        for atom in (monomial,pair):
            allowed.add(tuple(atom))
            allowed.add(tuple(-x for x in atom))
    require(len(allowed)==17,'invalid support construction')
    atoms=[r['atom'] for r in data['tables'][0]['rows']]
    require(len(atoms)==17 and {tuple(a) for a in atoms}==allowed,
            'the fixed17atom unit theorem does not apply')
    cdfs=[]
    for which,total_expected in enumerate((2048,2048,512)):
        rows=data['tables'][which]['rows']
        require([r['atom'] for r in rows]==atoms,'atom order differs across key/random tables')
        probabilities,cdf,total=distribution(rows)
        require(sum(probabilities)==1 and total==total_expected,'law normalization/mask mismatch')
        cdfs.append(cdf)
    f_rows=data['tables'][0]['rows']
    odd=sum(Fraction(r['numerator'],r['denominator']) for r in f_rows if sum(r['atom'])%2)
    require(odd==Fraction(9,256),'fixed-pool f failure bound has changed')
    g_rows=data['tables'][1]['rows']
    zero=sum(Fraction(r['numerator'],r['denominator']) for r in g_rows if not any(r['atom']))
    require(zero==Fraction(15,32),'fixed-pool g failure bound has changed')
    lifts=[]
    candidates=[]
    for residue in range(4):
        rows=[r for r in data['tables'][3]['rows']
              if (r['atom'][0]+r['atom'][2])%2+2*((r['atom'][1]+r['atom'][3])%2)==residue]
        probabilities,_,total=distribution(rows)
        count=(1,4,4,8)[residue]
        require(len(rows)==count and total==count and sum(probabilities)==Fraction(1,4),
                'conditional lift class is not the exact uniform fixed map')
        require(all(p==Fraction(1,4*count) for p in probabilities),'nonuniform conditional lift')
        indices=[atoms.index(r['atom']) for r in rows]
        lifts.append(indices*(8//count))
        if residue:
            candidates.extend([[residue,count-1,j,*r['atom']] for j,r in enumerate(rows)])
    return {'atoms':atoms,'cdf':cdfs,'word_mask':[2047,2047,511],
            'lift_index':lifts,'lift_mask':[0,3,3,7],'lift_candidates':candidates}


def check(root):
    expected=expected_tables(root)
    text=(root/'sampling_tables.h').read_text()
    for name,value in expected.items():
        match=re.search(r'\b'+name+r'\s*(?:\[\d+\])+\s*=\s*(\{[^;]+\});',text)
        require(match is not None,'missing compiled table '+name)
        actual=ast.literal_eval(match.group(1).replace('{','[').replace('}',']'))
        require(actual==value,'compiled table does not match the frozen exact law: '+name)
    return expected


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    check(Path(__file__).resolve().parent)
    print('PASS: exact17atom support, frozen JSON law, all compiled CDF/lift tables and fixed-pool probability assumptions')
