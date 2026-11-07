"""Cost-aware exhaustive GSA beta/d search for manuscript covariance routes.

All candidate reduced dimensions used by security.py are preserved.
This module does not model hybrid/dual/algebraic attacks or prove security.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import security
from matzov_cost import log2_cost,A,B,QUANTUM_A,QUANTUM_B
from math import log,pi,e
import numpy as np

def minimum(n,q,first,second,embedded=False,first_dim=None,quantum=False):
    first_dim=n if first_dim is None else first_dim
    keep,ds=security.grid(n,first_dim,int(embedded))
    logxi=log(second/first)/2
    logdet=keep*log(q)+first_dim*logxi+(log(second)/2 if embedded else 0)
    best=None
    for beta in range(40,int(max(ds))+1):
        shape=log(1.01295) if beta==40 else (log(beta/(2*pi*e))+log(pi*beta)/beta)/(2*(beta-1))
        margins=(2*beta-ds-1)*shape+logdet/ds-log(beta*second)/2
        ix=np.flatnonzero((ds>=beta)&(margins>=0))
        if not len(ix):continue
        # At fixed beta, formula is increasing with d; pick least feasible d.
        j=ix[0];d=int(ds[j]);score=float(log2_cost(beta,d,QUANTUM_A if quantum else A,QUANTUM_B if quantum else B))
        if best is None or score<best['matzov_bits']:
            best=dict(beta=beta,dimension=d,keep=int(keep[j]),
                      log_margin=float(margins[j]),matzov_bits=score,
                      cost_mode='MATZOV list_decoding-dw' if quantum else 'MATZOV list_decoding-classical',
                      core_classical=.292*beta,core_quantum=.257*beta,
                      log2_determinant=float(logdet[j]/log(2)))
    if best is None:raise ValueError('no passing beta/d')
    return best

def routes(n,q,laws,quantum=False):
    moms=security.moments(n,laws);ell=n//4
    orig=security.routes(n,q,laws)
    out={}
    for kind,index in [('coefficient',0),('covariance',2)]:
        for name,i,j,emb in [('f_g',0,1,False),('g_f',1,0,False),('r_m',2,3,True),('m_r',3,2,True)]:
            out[kind+'_'+name]=minimum(n,q,moms[i][index],moms[j][index],emb,quantum=quantum)
    z,u,a=laws[0]
    if a>0 and u<1:out['affine_f']=minimum(n,q,a/(4*(1-u)),moms[1][2],True,n-4,quantum)
    z,u,a=laws[1]
    if a>0 and u<1:
        av=a/(4*(1-u));nonzero=1-(z/(1-u))**ell
        out['affine_g']=minimum(n,q,av,moms[0][2],True,n-4,quantum)
        out['even_g']=minimum(n,q,av/nonzero,moms[0][2],False,n,quantum)
    z,u,a=laws[2]
    if a>0 and u<1:
        av=a/(4*(1-u))
        out['even_r']=minimum(n,q,av,moms[3][2],True,n,quantum)
        out['affine_r']=minimum(n,q,av,moms[3][2],True,n-4,quantum)
        out['affine_r']['subset_probability']=ell*u*(1-u)**(ell-1)
        out['affine_r']['subset_log2_probability']=log(ell*u,2)+(ell-1)*log(1-u,2)
        out['affine_r']['signed_monomial_guesses']=2*n
        out['affine_r']['matzov_bits_with_classical_all_guesses']=out['affine_r']['matzov_bits']+log(2*n,2)
    for key,row in out.items():
        if key in orig:
            for k in ('subset_probability','subset_log2_probability','zero_r_log2_probability'):
                if k in orig[key]:row[k]=orig[key][k]
    out['unconditional_minimum']=min((dict(route=k,**v) for k,v in out.items()
        if k.startswith(('coefficient_','covariance_'))),key=lambda row:row['matzov_bits'])
    out['paper_minimum']=min((dict(route=k,**v) for k,v in out.items()
        if k.startswith(('coefficient_','covariance_')) or k=='affine_f'),key=lambda row:row['matzov_bits'])
    out['all_modeled_minimum']=min((dict(route=k,**v) for k,v in out.items()
        if not k.endswith('minimum')),key=lambda row:row['matzov_bits'])
    out['all_modeled_minimum']['affine_r_convention']='if selected, no signed-monomial guess overhead is charged'
    return out

if __name__=='__main__':
    import json
    rows={
      'old_L3_q269':(1024,269,((.5,496/1024,16/1024),(.5,511/1024,1/1024),(.5,511/1024,1/1024),(.25,.5,.25))),
      'old_L5_q331':(1024,331,((84/256,3/256,169/256),(.5,124/256,4/256),(.5,124/256,4/256),(.25,.5,.25))),
      'original_L1_q211':(512,211,security.BASE_LAWS)
    }
    out={name:dict(n=n,q=q,laws=laws,estimates=routes(n,q,laws)) for name,(n,q,laws) in rows.items()}
    path=Path(__file__).with_name('existing_recost.json')
    path.write_text(json.dumps(out,indent=2)+'\n')
    for name,row in out.items():
        print(name,json.dumps({k:row['estimates'][k] for k in ('unconditional_minimum','paper_minimum','all_modeled_minimum')}))
