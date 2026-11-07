"""Generate the exact selected family contract and C tables; no KEM execution."""
from __future__ import annotations
import argparse
from fractions import Fraction
import hashlib
import importlib.util
import json
from math import gcd,isqrt,lcm
from pathlib import Path

HERE=Path(__file__).resolve().parent;REPO=HERE.parents[2]
SOURCE=REPO/'experiments/parameter_selection/refined/parameters_refined.json'
VERSION='Complementary-NTRU-Family-ACWC0-FO-20261107-v1'
SECTIONS=('main_recommendations','single_alternatives','double_alternatives','bat_target_profiles','strong_dfr_profiles')
PUBLIC_FUNCTIONS='keygen base_encrypt base_decrypt encrypt decrypt deterministic_encrypt encaps decaps randombytes shake256 pack unpack poly_mul poly_inv sample_poly sample_rm ct_poly_mul_n ct_poly_mul_avx2 ct_poly_inverse_n ct_poly_unit_n'.split()

def require(ok,message):
    if not ok:raise ValueError(message)

def order(a,m):
    x=1
    for k in range(1,m+1):
        x=x*a%m
        if x==1:return k
    raise ValueError('No multiplicative order')

def atom_rows():
    result=[[0,0,0,0]]
    for seed in ([1,0,0,0],[1,1,0,0]):
        a=list(seed)
        for _ in range(8):result.append(a);a=[-a[3],*a[:3]]
    require(len({tuple(a) for a in result})==17,'Atom support')
    return result

def c_array(name,ctype,values):
    def render(v):return '{'+','.join(render(x) if isinstance(x,list) else str(x) for x in v)+'}'
    dims=[];v=values
    while isinstance(v,list):dims.append(len(v));v=v[0]
    return f'static const {ctype} {name}'+''.join(f'[{n}]' for n in dims)+'='+render(values)+';'

def load_catalog():
    source=json.loads(SOURCE.read_text());chosen={}
    for section in SECTIONS:
        for index,row in enumerate(source[section]):
            n,q=row['n'],row['q'];mode=row.get('mode','single')
            m=row.get('external_M_bits',row.get('M',256));u=row.get('internal_u_bits',row.get('u',n//(4 if mode=='double' else 2)))
            k=row.get('output_K_bits',row.get('K',256));laws=[[str(Fraction(v)) for v in law] for law in row['laws']]
            semantic=dict(id=row['id'],n=n,q=q,mode=mode,laws=laws,external_message_bits=m,internal_residue_bits=u,shared_key_bits=k)
            if row['id'] in chosen:
                require(all(chosen[row['id']]['semantic'].get(k)==v for k,v in semantic.items()),'Conflicting duplicate profile '+row['id'])
                chosen[row['id']]['source_records'].append(f'{section}/{index}');continue
            require(n in (512,1024) and m in (128,256,512) and k==256,'Unsupported dimensions')
            require(mode in ('single','double') and u==n//(4 if mode=='double' else 2),'Residue geometry')
            require(q<=541 and all(q%d for d in range(2,isqrt(q)+1)),'Prime/range restriction')
            require(order(q,2*n)==(n//4)*order(q,8),'Exact unit theorem restriction')
            fs=list(map(Fraction,laws[0]));gs=list(map(Fraction,laws[1]));odd=(1-(1-2*fs[1])**(n//4))/2
            failure=1-odd;trials=256
            while failure.numerator**trials*(1<<256)>failure.denominator**trials:trials+=1
            require(trials<=272,'Unexpected f-pool schedule')
            require(gs[0]**(2*(n//4))<=Fraction(1,1<<256),'g-pool failure exceeds bound')
            cdfs=[];masks=[]
            for law in laws[:3]:
                z,mono,adj=map(Fraction,law);require(z>=0 and mono>0 and adj>=0 and z+mono+adj==1,'Invalid law')
                masses=[z]+[mono/8]*8+[adj/8]*8;den=lcm(*(p.denominator for p in masses))
                weights=[int(p*den) for p in masses];common=0
                for w in weights:common=gcd(common,w)
                weights=[w//common for w in weights];total=sum(weights)
                require(total&(total-1)==0 and total<=1<<32,'Non-dyadic CDF')
                cdf=[];v=0
                for w in weights:v+=w;cdf.append(v)
                cdfs.append(cdf);masks.append(total-1)
            require(laws[3]==(['1/2','0','1/2'] if mode=='double' else ['1/4','1/2','1/4']),'Message codebook law')
            word_bytes=2 if max(masks)<1<<16 else 4
            pk=((q**n).bit_length()+7)//8;ct=pk+m//8
            for key,value in [('pk',pk),('ct',ct)]:
                if key in row:require(row[key]==value,'Wire-size mismatch '+row['id'])
            semantic.update(version=VERSION,polynomial='x^n+1',P='1+x^(n/2)',orientation=[1,-1,1,-1],
                            message_encoding='W-adjacent-repeat-correct-first-max-v1' if mode=='double' else 'P-conditional-17-atom-v1',
                            byte_sampling={'atom_order':'zero;8 negacyclic monomial rotations;8 adjacent rotations',
                                           'coefficient_word_bytes':word_bytes,'coefficient_word_endian':'little',
                                           'message_coins':'one fixed byte per public block; zero classes consume an unused byte',
                                           'f_trials':trials,'g_trials':2},
                            fo={'context':'length-prefixed tag/version/parameter-id/pk',
                                'G':'message -> u || r/m coins','F':'u -> external-message mask',
                                'H':'actual received ciphertext || selected external message or rejection seed',
                                'rejection_seed_bytes':m//8,'decoder':('full syndrome; first absolute argmax; inverse over n/2 bits; equal halves' if mode=='double' else 'P-residue; inverse over n/2 bits')})
            digest=hashlib.sha256(json.dumps(semantic,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            chosen[row['id']]=dict(semantic=semantic,source_records=[f'{section}/{index}'],primary=section=='main_recommendations',
                                   cdfs=cdfs,masks=masks,word_bytes=word_bytes,f_trials=trials,pk_bytes=pk,ct_bytes=ct,
                                   wire_contract_sha256=digest,parameter_id='family20261107/'+digest,
                                   keygen_failure={'target':'each pool <=2^-256','f_exact_verified':True,'g_exact_verified':True,
                                                  'f_reject_numerator_hex':hex(failure.numerator),'f_reject_denominator_hex':hex(failure.denominator)},
                                   attributed_estimates={key:row[key] for key in ('C','Q','b','status') if key in row})
    require(len(chosen)==16,'Selected unique profile count')
    return list(chosen.values())

def generate():
    profiles=load_catalog();src=HERE/'src'
    spec=importlib.util.spec_from_file_location('family_radix_public',REPO/'implementations/c/common/ct_radix_generate.py')
    radix=importlib.util.module_from_spec(spec);spec.loader.exec_module(radix)
    metadata=['/* Generated exact selected family profiles. Do not edit. */','#include <stdint.h>']
    plans=['/* Generated exact public radix plans. */','#include "../../common/ct_radix.h"']
    tables=['/* Generated exact orbit CDFs and conditional message codebooks. */','#include <stdint.h>',c_array('atoms','int8_t',atom_rows())]
    ids=['#ifndef CNTRU_FAMILY_PROFILE_IDS_H','#define CNTRU_FAMILY_PROFILE_IDS_H']
    atoms=atom_rows();lift=[]
    for cls in (1,2,3):
        rows=[a for a in atoms if ((a[0]+a[2])&1)+2*((a[1]+a[3])&1)==cls]
        require(len(rows)==(4 if cls!=3 else 8),'Conditional codebook cardinality')
        lift.extend([[cls,len(rows)-1,i,*a] for i,a in enumerate(rows)])
    tables.append(c_array('lift_candidates','int8_t',lift));tables.append(c_array('double_adjacent','int8_t',atoms[9:]))
    for number,p in enumerate(profiles,1):
        semantic=p['semantic'];n,q=semantic['n'],semantic['q'];macro='CNTRU_PROFILE_'+semantic['id'].upper()
        require(macro.replace('_','').isalnum(),'Unsafe profile token');ids.append(f'#define {macro} {number}')
        cond=('#if' if number==1 else '#elif')+f' CNTRU_FAMILY_PROFILE == {number}'
        for lines in (metadata,plans,tables):lines.append(cond)
        values=dict(CNTRU_N=n,CNTRU_Q=q,CNTRU_Q_INVERSE_BITS=(q-2).bit_length(),CNTRU_DOUBLE=int(semantic['mode']=='double'),CNTRU_MESSAGE_BYTES=semantic['external_message_bits']//8,
                    CNTRU_U_BYTES=semantic['internal_residue_bits']//8,CNTRU_PK_BYTES=p['pk_bytes'],CNTRU_CORE_BYTES=p['pk_bytes'],
                    CNTRU_CT_BYTES=p['ct_bytes'],CNTRU_WORD_BYTES=p['word_bytes'],CNTRU_F_CANDIDATES=p['f_trials'])
        metadata.extend(f'#define {k} {v}' for k,v in values.items())
        metadata.extend([f'#define CNTRU_PARAMETER_ID {json.dumps(p["parameter_id"])}',f'#define CNTRU_PROFILE_ID {json.dumps(semantic["id"])}',
                         f'#define CNTRU_VERSION {json.dumps(VERSION)}',f'#define CNTRU_Q_RECIPROCAL UINT64_C({((1<<32)+q-1)//q})',
                         f'#define CNTRU_NAMESPACE(name) cntru_family_p{number:02d}_##name'])
        tables.extend([c_array('cdf','uint32_t',p['cdfs']),c_array('word_mask','uint32_t',p['masks'])])
        plans.extend([radix.emit(radix.plan(n,q),'cntru_family_radix_plan')])
        p.update(number=number,macro=macro,symbol_prefix=f'cntru_family_p{number:02d}_')
    for lines in (metadata,plans,tables):lines.extend(['#else','#error "Unsupported CNTRU_FAMILY_PROFILE"','#endif'])
    ids.append('#endif')
    aliases=[f'#define cntru_{name} CNTRU_NAMESPACE({name})' for name in PUBLIC_FUNCTIONS]+['#define cntru_sk CNTRU_NAMESPACE(sk)','#define cntru_rng CNTRU_NAMESPACE(rng)']
    config='''#ifndef CNTRU_FAMILY_CONFIG_H
#define CNTRU_FAMILY_CONFIG_H
#include "profile_ids.h"
#ifndef CNTRU_FAMILY_PROFILE
#error "Compile with a profile selector from profile_ids.h"
#endif
#include "profiles.h"
#define CNTRU_HALF (CNTRU_N/2)
#define CNTRU_BLOCKS (CNTRU_N/4)
/* The inverse always lives over n/2 bits, including D with u=n/4. */
#define CNTRU_U_WORDS (CNTRU_HALF/64)
#define CNTRU_KEY_BYTES 32
#define CNTRU_SAMPLE_BYTES (CNTRU_BLOCKS*CNTRU_WORD_BYTES)
#define CNTRU_RHO_BYTES (CNTRU_SAMPLE_BYTES+CNTRU_BLOCKS)
#define CNTRU_COINS_BYTES (CNTRU_U_BYTES+CNTRU_RHO_BYTES)
#define CNTRU_F_POOL_BYTES (CNTRU_F_CANDIDATES*CNTRU_SAMPLE_BYTES)
#define CNTRU_G_POOL_BYTES (2*CNTRU_SAMPLE_BYTES)
#define CNTRU_REDUCTION_BIAS (CNTRU_Q*524288)
'''+ '\n'.join(aliases)+'\n#endif\n'
    bound=1024*270**2;require(12289*18433>2*bound and 998244353>2*bound,'Auxiliary CRT lift bound')
    catalog={'version':VERSION,'selection_source':str(SOURCE.relative_to(REPO)),
             'G28':'excluded by explicit user scope','ntt_bounds':{'maximum_q':541,'maximum_n':1024,'centered_input':270,
             'maximum_absolute_convolution':bound,'crt_product':12289*18433,'crt_unique_lift_verified':True},'profiles':profiles}
    return {src/'profiles.h':'\n'.join(metadata)+'\n',src/'profile_ids.h':'\n'.join(ids)+'\n',src/'config.h':config,
            src/'sampling_tables.h':'\n'.join(tables)+'\n',src/'radix_plans.h':'\n'.join(plans)+'\n',HERE/'profiles.json':json.dumps(catalog,indent=2)+'\n'}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    for path,text in generate().items():
        if args.check:require(path.exists() and path.read_text()==text,'Generated drift: '+str(path))
        else:path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
    print('PASS:16 exact selected profiles, dyadic CDFs, unit orders, pool bounds, radix plans and centered CRT bounds; no KEM executed')

if __name__=='__main__':main()
