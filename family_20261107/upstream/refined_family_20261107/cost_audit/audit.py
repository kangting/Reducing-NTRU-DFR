"""Independent costs and exact conditional event probabilities.

This audits arithmetic in a stated GSA model; it does not prove security.
The input may be selected.json from either the old or revised snapshot.
"""
from pathlib import Path
from fractions import Fraction as F
import argparse,json,math,sys
import numpy as np
from cost_matrix import single,grids,derived_moments

def prob(p):
    p=F(p)
    return dict(exact=str(p),probability=float(p),
        log2_probability=(math.log2(p.numerator)-math.log2(p.denominator))if p else None)

def events(n,laws):
    ell=n//4
    z,u,a=laws[0];pf=(1-(1-2*u)**ell)/2
    out={'affine_f':prob(ell*u*(1-u)**(ell-1)/pf)}
    z,u,a=laws[1];pg=1-z**ell
    out['affine_g']=prob(ell*u*(1-u)**(ell-1)/pg)
    out['even_g']=prob(((1-u)**ell-z**ell)/pg)
    z,u,a=laws[2]
    out['even_r']=prob((1-u)**ell)
    out['affine_r']=prob(ell*u*(1-u)**(ell-1))
    out['zero_r']=prob(z**ell)
    for k,v in out.items():
        v['meaning']='exact event coverage under accepted keys / fresh r; not attack success or general-key complexity'
    return out

def core(n,q,v1,v2,embedded=False,fd=None):
    fd=n if fd is None else fd
    keeps,ds,bs,shape,costs=grids(n,fd,int(embedded))
    logdet=keeps*math.log(q)+fd*.5*math.log(v2/v1)+(math.log(v2)/2 if embedded else 0)
    margins=shape+logdet/ds-.5*math.log(v2)
    feasible=(ds>=bs)&(margins>=0)
    ii=np.flatnonzero(np.any(feasible,axis=1))[0]
    jj=int(np.argmax(np.where(feasible[ii],margins[ii],-np.inf)))
    beta=int(bs[ii,0]);d=int(ds[0,jj])
    return dict(beta=beta,dimension=d,keep=int(keeps[0,jj]),
        classical=.292*beta,quantum=.257*beta,
        dimension_convention='minimum feasible beta; d maximizes GSA margin at that beta')

def audit(row):
    n,q=row['n'],row['q'];ell=n//4
    assert n>=8 and n&(n-1)==0 and q>2 and q%2
    assert all(q%d for d in range(2,math.isqrt(q)+1))
    def order(modulus):
        value=q%modulus;degree=1
        while value!=1:value=value*q%modulus;degree+=1
        return degree
    assert order(2*n)==ell*order(8)
    laws=tuple(tuple(F(v)for v in a)for a in row['laws'])
    moms=derived_moments(n,laws);paths={};ev=events(n,laws)
    def add(name,v1,v2,emb=False,fd=None):
        result=single(n,q,float(v1),float(v2),emb,fd)
        result['core_svp_optimum']=core(n,q,float(v1),float(v2),emb,fd)
        for mode in ('classical','quantum'):
            beta=result[mode]['beta']
            result[mode]['core_classical_at_same_beta']=.292*beta
            result[mode]['core_quantum_at_same_beta']=.257*beta
            if 'costs'in row:
                expected=row['costs'][mode][name]
                assert abs(result[mode]['bits']-expected['matzov_bits'])<1e-8
        result['coverage']=ev[name] if name in ev else dict(probability=1,exact='1',log2_probability=0,meaning='ordinary structural path without additional subset conditioning')
        result['lattice_reduction_success_probability']='not independently measured; the heuristic GSA inequality is a feasibility proxy'
        paths[name]=result
    for kind,index in [('coefficient',0),('covariance',1)]:
        for name,i,j,emb in [('f_g',0,1,False),('g_f',1,0,False),('r_m',2,3,True),('m_r',3,2,True)]:
            add(kind+'_'+name,moms[i][index],moms[j][index],emb)
    for name,index,other in [('affine_f',0,1),('affine_g',1,0),('affine_r',2,3)]:
        z,u,a=laws[index];add(name,a/(4*(1-u)),moms[other][1],True,n-4)
    z,u,a=laws[1]
    add('even_g',a/(4*(1-u))/(1-(z/(1-u))**ell),moms[0][1],False,n)
    z,u,a=laws[2];add('even_r',a/(4*(1-u)),moms[3][1],True,n)
    paths['affine_r']['normalization']=dict(signed_monomial_candidates=2*n,
        convention='free normalization in conservative diagnostic minimum',
        classical_exhaustive_guess_log2_overhead=math.log2(2*n),
        warning='Adding this overhead is an alternate implementation convention, not proof that guesses must be done independently.')
    mins={mode:min((dict(route=k,**v[mode],coverage=v['coverage'])for k,v in paths.items()),key=lambda x:x['bits'])for mode in ('classical','quantum')}
    ordinary={mode:min((dict(route=k,**v[mode])for k,v in paths.items()if k.startswith(('coefficient_','covariance_'))),key=lambda x:x['bits'])for mode in ('classical','quantum')}
    message=row.get('old_certificate',{})
    M=row.get('external_message_bits',message.get('external_message_bits',256))
    u=row.get('internal_message_bits',message.get('internal_message_bits',n//2))
    K=row.get('shared_key_bits',256);search=min(M,u)
    poly=((q**n-1).bit_length()+7)//8
    return dict(id=row['id'],n=n,q=q,laws=row['laws'],events=ev,paths=paths,
        exact_unit_condition=dict(prime_q=True,order_2n=order(2*n),order_8=order(8),block_count=ell,passes=True),
        wire_sizes=dict(public_key_bytes=poly,ciphertext_bytes=poly+M//8,total_bytes=2*poly+M//8,mask_bytes=M//8,headers_included=False),
        all_diagnostic_minima=mins,ordinary_minima=ordinary,
        message_query_bounds=dict(external_M=M,internal_u=u,output_K=K,
          min_seed_entropy_bits=search,classical_candidate_queries_log2=search,
          ideal_quantum_oracle_queries_log2=search/2,
          meaning='Public verification of candidate FO message or ACWC0 internal seed; oracle-query upper bounds, not gate-model security bits'),
        success_convention='No multiplication or division by subset probability is used to turn a rare-event path into arbitrary fixed-key recovery cost.')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('input');ap.add_argument('--all',action='store_true');ap.add_argument('--out',default=str(Path(__file__).with_name('audit.json')));args=ap.parse_args()
    selected={'S512_M256_AP_compact','S1024_M256_A','D512_M128_W_experimental','D1024_M256_W_experimental'}
    data=json.loads(Path(args.input).read_text())
    if isinstance(data,dict):data=data.get('selected_profiles',data.get('rows',[]))
    rows=[audit(row)for row in data if args.all or row['id']in selected]
    result=dict(cost_model='GSA manuscript feasibility; MATZOV list_decoding cost port from lattice-estimator 5ba00f5; not the full estimator attack suite',
      exact_event_formulas=dict(ell='n/4',accept_f='[1-(1-2U_f)^ell]/2',accept_g='1-z_g^ell',
      affine_f='ell U_f (1-U_f)^(ell-1) / accept_f',
      affine_g='ell U_g (1-U_g)^(ell-1) / accept_g',
      even_g='[(1-U_g)^ell-z_g^ell]/accept_g',
      affine_r='ell U_r (1-U_r)^(ell-1)',even_r='(1-U_r)^ell'),
      terminology='even_g and even_r mean zero monomial blocks; they do not mean all even-parity monomial counts',
      rows=rows)
    Path(args.out).write_text(json.dumps(result,indent=2)+'\n')
    for r in rows:print(r['id'],'f-oneodd',r['events']['affine_f']['probability'],'r-oneodd',r['events']['affine_r']['probability'],'C/Q',r['all_diagnostic_minima']['classical']['bits'],r['all_diagnostic_minima']['quantum']['bits'],flush=True)
