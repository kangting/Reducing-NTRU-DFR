#!/usr/bin/env python3
"""Generate/check C constants only after root's frozen profiles pass checks."""
import argparse
from fractions import Fraction
from functools import reduce
import importlib.util
import json
from math import gcd,lcm,isqrt
from pathlib import Path
import subprocess
import sys

EXPECTED_WIRE_HASHES={
    307:'b3aa1f09c91658219038d9ebd5d4eafd67aa72e6008995a6e9f460702794d526',
    331:'a502412ff05764d1b79a2e9873f7736db8a1c9219e7d7990fff393db89882d42',
    373:'90de0f90dc821d64cf3457657b23d38da8077c82db8760619c5266eacb49d25f',
}


def require(value,message):
    if not value:raise ValueError(message)


def distribution(rows):
    probabilities=[Fraction(r['numerator'],r['denominator']) for r in rows]
    denominator=lcm(*(p.denominator for p in probabilities))
    weights=[p.numerator*(denominator//p.denominator) for p in probabilities]
    divisor=reduce(gcd,weights)
    result=[];total=0
    for w in weights:total+=w//divisor;result.append(total)
    require(total>0 and total&(total-1)==0,'CDF total is not a power of two')
    return result,total


def array(name,ctype,value):
    def render(v):return '{'+','.join(render(x) if isinstance(x,list) else str(x) for x in v)+'}'
    dimensions=[];v=value
    while isinstance(v,list):dimensions.append(len(v));v=v[0]
    return 'static const '+ctype+' '+name+''.join(f'[{n}]' for n in dimensions)+' = '+render(value)+';'


def generate(root):
    source=root/'profiles.py'
    subprocess.run([sys.executable,str(source),'--check'],check=True,stdout=subprocess.PIPE,text=True)
    spec=importlib.util.spec_from_file_location('cntru_frozen_profiles',source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    profiles=[module.load_profile(q) for q in (307,331,373)]
    common=['/* Generated from checked parameters/q*.json. */','#include <stdint.h>']
    metadata=common.copy();tables=common.copy()
    atoms=[r['atom'] for r in profiles[0]['tables'][0]['rows']]
    allowed={(0,0,0,0)}
    for j in range(4):
        monomial=[0]*4;monomial[j]=1
        pair=monomial.copy();pair[(j+1)%4]+=1 if j<3 else -1
        for a in (monomial,pair):allowed.add(tuple(a));allowed.add(tuple(-x for x in a))
    require(len(atoms)==17 and {tuple(a) for a in atoms}==allowed,'unsupported atom set')
    tables.append(array('atoms','int8_t',atoms))
    for index,p in enumerate(profiles):
        q=p['q'];condition=('#if' if not index else '#elif')+f' CNTRU_Q == {q}'
        require(p['wire_contract_sha256']==EXPECTED_WIRE_HASHES[q],'unreviewed wire-contract change')
        require(all(q%d for d in range(2,isqrt(q)+1)),'q is not prime')
        require(pow(q,512,2048)==1 and pow(q,256,2048)!=1,'unit-theorem field degree')
        require(pow(q,2,8)==1 and q%8!=1,'unit-theorem block field degree')
        require(p['tables'][3]['rows']==profiles[0]['tables'][3]['rows'],'message-law drift')
        metadata.append(condition);tables.append(condition)
        metadata.extend([f'#define CNTRU_PK_BYTES {p["pk_bytes"]}',f'#define CNTRU_CORE_BYTES {p["core_bytes"]}',
                         f'#define CNTRU_CT_BYTES {p["ct_bytes"]}',f'#define CNTRU_VERSION {json.dumps(p["version"])}',
                         f'#define CNTRU_PARAMETER_ID {json.dumps(p["parameter_id"])}',
                         f'#define CNTRU_Q_RECIPROCAL UINT64_C({((1<<32)+q-1)//q})',
                         f'#define CNTRU_Q3 UINT64_C({q**3})',
                         f'#define CNTRU_Q3_RECIPROCAL UINT64_C({((1<<64)+q**3-1)//q**3})',
                         f'#define CNTRU_Q3_LOG2 {(q**3).bit_length()-1}'])
        cdfs=[];masks=[]
        for t in p['tables'][:3]:
            require([r['atom'] for r in t['rows']]==atoms,'atom order drift')
            cdf,total=distribution(t['rows']);cdfs.append(cdf);masks.append(total-1)
        tables.extend([array('cdf','uint16_t',cdfs),array('word_mask','uint16_t',masks)])
    metadata.append('#endif');tables.append('#endif')
    candidates=[]
    for residue in (1,2,3):
        rows=[r for r in profiles[0]['tables'][3]['rows'] if (r['atom'][0]+r['atom'][2])%2+2*((r['atom'][1]+r['atom'][3])%2)==residue]
        expected=(4,4,8)[residue-1]
        require(len(rows)==expected,'conditional class size')
        require(all(Fraction(r['numerator'],r['denominator'])==Fraction(1,4*expected) for r in rows),'conditional law')
        candidates.extend([[residue,expected-1,j,*r['atom']] for j,r in enumerate(rows)])
    tables.append(array('lift_candidates','int8_t',candidates))
    return {'profiles.h':'\n'.join(metadata)+'\n','sampling_tables.h':'\n'.join(tables)+'\n'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args();root=Path(__file__).resolve().parent
    for name,text in generate(root).items():
        target=root/name
        if args.check:require(target.is_file() and target.read_text()==text,'generated file differs: '+name)
        else:target.write_text(text)
    print('PASS: frozen wire profiles, exact17atom rows and normalized CDF/domain constants')
