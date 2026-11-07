"""Generalized manuscript GSA cost models for four-coefficient block laws.

Laws are total masses (zero, signed monomials, signed adjacent pairs).
All masses within either eight-element orbit are equal. This module evaluates
heuristic length criteria; it does not run BKZ or certify concrete security.
The exact key-acceptance law is valid only for primes with
ord_{2n}(q)/ord_8(q)=n/4. Use admissible() to enforce that condition.
"""
from functools import lru_cache
from math import log, log1p, sqrt, pi, e, exp
import json
import numpy as np

BASE_LAWS = ((.5,9/256,119/256),(15/32,85/256,51/256),
             (7/16,27/64,9/64),(.25,.5,.25))

def order(q, mod):
    if q%2 == 0:
        return None
    x=q%mod;k=1
    while x!=1:
        x=x*q%mod;k+=1
        if k>mod:return None
    return k

def isprime(q):
    if q<2:return False
    if q%2==0:return q==2
    return all(q%d for d in range(3,int(sqrt(q))+1,2))

def admissible(n,q):
    if not isinstance(n,(int,np.integer)) or n<8 or n&(n-1):
        return False
    if not isinstance(q,(int,np.integer)) or q<3 or q%2==0 or not isprime(q):
        return False
    base_order=order(q,8)
    return base_order is not None and order(q,2*n)==n//4*base_order

def moments(n,laws=BASE_LAWS):
    ell=n//4
    out=[]
    for i,(z,u,a) in enumerate(laws):
        if min(z,u,a)<0 or abs(z+u+a-1)>1e-10:raise ValueError('invalid law')
        if i==0:
            bias=1-2*u
            den=1-bias**ell
            if den<=0:raise ValueError('zero f acceptance')
            u=u*(1+bias**(ell-1))/den
            a=a*(1-bias**(ell-1))/den
        elif i==1:
            den=1-z**ell
            if den<=0:raise ValueError('zero g acceptance')
            u/=den;a/=den
        v=u/4+a/2;k=a/4
        w=sqrt(max(0,v*v-2*k*k))
        out.append((v,k,w))
    return out

@lru_cache(None)
def grid(n, first_dim, embedded):
    keep=np.arange(4,n+1,4,dtype=float)
    dim=first_dim+keep+embedded
    return keep,dim

def best_at(beta,n,q,first,second,embedded=False,first_dim=None):
    if first_dim is None:first_dim=n
    if first<=0 or second<=0:raise ValueError('zero width')
    keep,dim=grid(n,first_dim,int(embedded))
    logxi=log(second/first)/2
    logdet=keep*log(q)+first_dim*logxi+(log(second)/2 if embedded else 0)
    shape=(log(1.01295) if beta==40 else
           (log(beta/(2*pi*e))+log(pi*beta)/beta)/(2*(beta-1)))
    margin=(2*beta-dim-1)*shape+logdet/dim-log(beta*second)/2
    margin=np.where(dim>=beta,margin,-np.inf)
    ix=int(np.argmax(margin))
    return dict(beta=int(beta),dimension=int(dim[ix]),keep=int(keep[ix]),
                log_margin=float(margin[ix]),log2_determinant=float(logdet[ix]/log(2)))

def estimate(n,q,first,second,embedded=False,first_dim=None,full_scan=False):
    first_dim=n if first_dim is None else first_dim
    maximum=first_dim+n+int(embedded)
    if full_scan:
        for beta in range(40,maximum+1):
            row=best_at(beta,n,q,first,second,embedded,first_dim)
            if row['log_margin']>=0:break
        else:raise ValueError('no passing beta')
    else:
        lo=40;hi=maximum
        if best_at(hi,n,q,first,second,embedded,first_dim)['log_margin']<0:
            raise ValueError('no passing beta')
        while lo<hi:
            mid=(lo+hi)//2
            if best_at(mid,n,q,first,second,embedded,first_dim)['log_margin']>=0:hi=mid
            else:lo=mid+1
        row=best_at(lo,n,q,first,second,embedded,first_dim)
    row.update(classical=.292*row['beta'],quantum=.257*row['beta'])
    return row

def trivial_route(subset):
    return dict(beta=0,dimension=0,keep=0,log_margin=None,
                log2_determinant=None,classical=0.,quantum=0.,
                subset_probability=subset,status='zero conditional unknown')

def subset_log(row, natural_log_probability):
    """Keep log probability even when the floating-point probability underflows."""
    row['subset_log2_probability']=natural_log_probability/log(2)
    return row

def routes(n,q,laws=BASE_LAWS,full_scan=False):
    if not admissible(n,q):raise ValueError('unsupported acceptance field condition')
    moms=moments(n,laws);ell=n//4
    out={}
    for kind,index in [('coefficient',0),('covariance',2)]:
        for name,i,j,emb in [('f_g',0,1,False),('g_f',1,0,False),
                             ('r_m',2,3,True),('m_r',3,2,True)]:
            out[kind+'_'+name]=estimate(n,q,moms[i][index],moms[j][index],emb,
                                        full_scan=full_scan)
    z,u,a=laws[0]
    accept=(1-(1-2*u)**ell)/2
    subset=ell*u*(1-u)**(ell-1)/accept
    log_subset=log(ell*u)+(ell-1)*log1p(-u)-log(accept)
    avar=a/(4*(1-u))
    if avar>0:
        out['affine_f']=estimate(n,q,avar,moms[1][2],True,n-4,full_scan)
        out['affine_f']['subset_probability']=subset
        subset_log(out['affine_f'],log_subset)
    elif subset>0:
        out['affine_f']=trivial_route(subset)
        subset_log(out['affine_f'],log_subset)
    z,u,a=laws[1]
    accept_g=1-z**ell
    subset_g=ell*u*(1-u)**(ell-1)/accept_g
    avar_g=a/(4*(1-u)) if u<1 else 0
    if avar_g>0:
        out['affine_g']=estimate(n,q,avar_g,moms[0][2],True,n-4,full_scan)
        out['affine_g']['subset_probability']=subset_g
        if u>0:
            subset_log(out['affine_g'],log(ell*u)+(ell-1)*log1p(-u)-log(accept_g))
        even_prob=((1-u)**ell-z**ell)/accept_g
        nonzero=1-(z/(1-u))**ell
        out['even_g']=estimate(n,q,avar_g/nonzero,moms[0][2],False,n,full_scan)
        out['even_g']['subset_probability']=even_prob
        log_even=ell*log1p(-u)
        zero_even_ratio=exp(ell*log(z)-log_even) if z>0 else 0
        subset_log(out['even_g'],log_even+log1p(-zero_even_ratio)-log(accept_g))
    elif subset_g>0:
        out['affine_g']=trivial_route(subset_g)
        subset_log(out['affine_g'],log(ell*u)+(ell-1)*log1p(-u)-log(accept_g))
    z,u,a=laws[2]
    if u<1 and a>0:
        avar_r=a/(4*(1-u))
        out['even_r']=estimate(n,q,avar_r,moms[3][2],True,n,full_scan)
        out['even_r']['subset_probability']=(1-u)**ell
        subset_log(out['even_r'],ell*log1p(-u))
        out['even_r']['zero_r_probability']=z**ell
        out['even_r']['zero_r_log2_probability']=ell*log(z,2) if z>0 else None
    elif u<1 and z>0:
        out['even_r']=trivial_route(z**ell)
        subset_log(out['even_r'],ell*log(z))
    out['minimum']=min((dict(route=k,**v) for k,v in out.items()),key=lambda x:x['beta'])
    out['benchmark_minimum']=min((dict(route=k,**v) for k,v in out.items()
        if k.startswith(('coefficient_','covariance_')) or k=='affine_f'),
        key=lambda x:x['beta'])
    return out

def threshold_margins(n,q,laws,target_beta):
    """All routes require beta>=target iff they fail at target-1 (monotonic model)."""
    moms=moments(n,laws);beta=target_beta-1
    vals=[]
    for i,j,emb in [(0,1,False),(1,0,False),(2,3,True),(3,2,True)]:
        vals.append(best_at(beta,n,q,moms[i][2],moms[j][2],emb)['log_margin'])
    z,u,a=laws[0]
    if 0<u<1 and a>0:
        vals.append(best_at(beta,n,q,a/(4*(1-u)),moms[1][2],True,n-4)['log_margin'])
    elif 0<u<1 and z>0:
        vals.append(float('inf'))
    z,u,a=laws[1]
    if u<1 and a>0:
        av=a/(4*(1-u))
        vals.append(best_at(beta,n,q,av,moms[0][2],True,n-4)['log_margin'])
        nonzero=1-(z/(1-u))**(n//4)
        if nonzero>0:
            vals.append(best_at(beta,n,q,av/nonzero,moms[0][2],False,n)['log_margin'])
    elif 0<u<1 and z>0:
        vals.append(float('inf'))
    z,u,a=laws[2]
    if u<1 and a>0:
        vals.append(best_at(beta,n,q,a/(4*(1-u)),moms[3][2],True,n)['log_margin'])
    elif u<1 and z>0:
        vals.append(float('inf'))
    return vals

def subset_diagnostics(n,q,laws=BASE_LAWS):
    """Additional rare subsets, including guessed normalization of r.

    The affine-r target needs a signed-monomial guess (2n candidates), since
    dividing r and m rotates the ciphertext offset. Report the unadjusted
    sieve exponent plus the classical exhaustive-guess allowance separately.
    These probabilities are not empirical attack success rates.
    """
    ell=n//4;moms=moments(n,laws)
    out={}
    for name,(z,u,a) in zip(('f','g','r','m'),laws):
        entropy=-sum(p*log(p,2) for p in (z,u,a) if p>0)+3*(u+a)
        out[name]=dict(all_zero=z**ell,all_monomial=u**ell,
                       all_adjacent=a**ell,all_even=(1-u)**ell,
                       exactly_one_odd=ell*u*(1-u)**(ell-1),
                       unconditional_shannon_entropy=ell*entropy)
        out[name]['event_probability_conditioning']='before key acceptance and message conditioning'
        out[name]['event_negative_log2_probability']={
            'all_zero':-ell*log(z,2) if z>0 else None,
            'all_monomial':-ell*log(u,2) if u>0 else None,
            'all_adjacent':-ell*log(a,2) if a>0 else None,
            'all_even':-ell*log(1-u,2) if u<1 else None,
            'exactly_one_odd':-log(ell*u,2)-(ell-1)*log(1-u,2) if 0<u<1 else None}
        if u<1:
            density=a/(1-u)
            h=-sum(p*log(p,2) for p in (density,1-density) if p>0)+3*density
            out[name]['even_conditional_nonzero_block_probability']=density
            out[name]['one_odd_remaining_shannon_entropy']=(ell-1)*h
        if name in ('f','g'):
            accepted=(1-(1-2*u)**ell)/2 if name=='f' else 1-z**ell
            one_monomial=(log(ell*u)+(ell-1)*log(z)-log(accepted))/log(2) if u>0 and z>0 else None
            one_adjacent=(log(ell*a)+(ell-1)*log(z)-log(accepted))/log(2) if name=='g' and a>0 and z>0 else None
            out[name]['single_nonzero_monomial_log2_probability_accepted']=one_monomial
            out[name]['single_nonzero_adjacent_log2_probability_accepted']=one_adjacent
    z,u,a=laws[2]
    if u<1 and a>0:
        row=estimate(n,q,a/(4*(1-u)),moms[3][2],True,n-4)
        row.update(subset_probability=ell*u*(1-u)**(ell-1),
                   signed_monomial_guesses=2*n,
                   classical_with_all_guesses=row['classical']+log(2*n,2))
        if u>0:
            subset_log(row,log(ell*u)+(ell-1)*log1p(-u))
        out['affine_r_diagnostic']=row
    return out

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--n',type=int,default=512)
    parser.add_argument('--q',type=int,default=211)
    parser.add_argument('--out')
    parser.add_argument('--full-scan',action='store_true')
    args=parser.parse_args()
    result=dict(n=args.n,q=args.q,laws=BASE_LAWS,
                estimates=routes(args.n,args.q,full_scan=args.full_scan))
    text=json.dumps(result,indent=2)
    if args.out:open(args.out,'w').write(text+'\n')
    print(text)
