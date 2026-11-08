"""Reproduce the manuscript's selected GSA/MATZOV recovery diagnostics.

Run from this directory: python3 security_audit.py
Requires Python >= 3.10 and NumPy. No Sage, external estimator, or network.
This evaluates a heuristic success criterion; it does not run BKZ.
Input probabilities and event coverages use exact fractions. Feasibility and
work estimates use IEEE double precision, as in the original diagnostic.
"""
from fractions import Fraction as F
from pathlib import Path
import json
import math
import numpy as np
from cost_model import grids, derived_moments

ROOT = Path(__file__).resolve().parent


def probability(p):
    p = F(p)
    return dict(exact=str(p), log2=math.log2(p.numerator)-math.log2(p.denominator)
                if p else None, value=float(p))


def cost(n, q, v1, v2, embedded=False, first_dimension=None, extra=0):
    """Second-vector variance fixes embedding height and projected norm.

    For extra known-zero equations, first_dimension omits its own zero
    quartet; the second vector's known zero quartet adds four constraints.
    Q_at_C uses the same (dimension,beta) that minimizes classical work.
    Q_min is also saved to expose possible changes of convention.
    """
    fd = n if first_dimension is None else first_dimension
    keeps, ds, bs, shape, costs = grids(n, fd, int(embedded))
    v1, v2 = float(v1), float(v2)
    logdet = ((keeps+extra)*math.log(q)+fd/2*math.log(v2/v1)
              +(math.log(v2)/2 if embedded else 0))
    margin = shape+logdet/ds-math.log(v2)/2
    ok = (ds >= bs) & (margin >= 0) & (keeps <= n-extra)
    C = np.where(ok, costs['classical'], np.inf)
    i, j = np.unravel_index(np.argmin(C), C.shape)
    Q = np.where(ok, costs['quantum'], np.inf)
    qi, qj = np.unravel_index(np.argmin(Q), Q.shape)
    assert np.isfinite(C[i,j])
    return dict(C=float(C[i,j]), Q_at_C=float(Q[i,j]),
                d=int(ds[0,j]), beta=int(bs[i,0]), keep=int(keeps[0,j]),
                feasibility_log_margin=float(margin[i,j]),
                Q_min=float(Q[qi,qj]), Q_min_d=int(ds[0,qj]),
                Q_min_beta=int(bs[qi,0]), variance_first=v1,
                variance_second=v2, first_dimension=fd, extra_rank=extra,
                embedding=embedded)


def profile(row):
    n, q, L = row['n'], row['q'], row['n']//4
    laws = [tuple(map(F,x)) for x in row['laws']]
    moms = derived_moments(n, laws)
    zf, uf, af = laws[0]
    zg, ug, ag = laws[1]
    zr, ur, ar = laws[2]
    zm, um, am = laws[3]
    accf = (1-(1-2*uf)**L)/2
    accg = 1-zg**L
    events = {
        'affine_f': L*uf*(1-uf)**(L-1)/accf,
        'affine_g': L*ug*(1-ug)**(L-1)/accg,
        'even_g': ((1-ug)**L-zg**L)/accg,
        'affine_r': L*ur*(1-ur)**(L-1),
        'even_r': (1-ur)**L,
        'message_factor': (1-um)**L,
    }
    routes = {}
    def add(name,v1,v2,embedded=False,fd=None,extra=0,event=F(1),
            event_scope='all accepted keys and honest ciphertexts',guess=0):
        routes[name] = dict(cost(n,q,v1,v2,embedded,fd,extra),
            coverage=probability(event), event_scope=event_scope,
            maximum_signed_monomial_guesses=guess,
            guess_work_included=False,
            recovery_success='not measured; GSA feasibility is a proxy')
    # Eight ordinary paths, with either coefficient or covariance-volume proxy.
    for kind,k in [('coefficient',0),('covariance',1)]:
        for name,i,j,emb in [('f_g',0,1,False),('g_f',1,0,False),
                            ('r_m',2,3,True),('m_r',3,2,True)]:
            add(kind+'_'+name,moms[i][k],moms[j][k],emb)
    for name,i,j in [('affine_f',0,1),('affine_g',1,0),('affine_r',2,3)]:
        z,u,a = laws[i]
        add(name,a/(4*(1-u)),moms[j][1],True,n-4,event=events[name],
            event_scope='accepted keys' if i<2 else 'fresh ciphertext randomness',
            guess=2*n if i==2 else 0)
    add('even_g',ag/(4*(1-ug))/(1-(zg/(1-ug))**L),moms[0][1],
        event=events['even_g'],event_scope='accepted keys')
    add('even_r',ar/(4*(1-ur)),moms[3][1],True,
        event=events['even_r'],event_scope='fresh ciphertext randomness')
    # Factored-message relation: no monomial message blocks (always for D).
    bm, ra = am/(4*(1-um)), ar/(4*(1-ur))
    for name,v1,v2 in [('factor_r_bm_coeff',moms[2][0],bm),
                       ('factor_r_bm_cov',moms[2][1],bm),
                       ('factor_bm_r_cov',bm,moms[2][1])]:
        add(name,v1,v2,True,event=events['message_factor'],
            event_scope='all D ciphertexts; no-monomial message event for S')
    for name,v1,v2,fd,e,guesses in [
        ('factor_even_r',ra,bm,n,events['even_r'],0),
        ('factor_even_r_reverse',bm,ra,n,events['even_r'],0),
        ('factor_affine_r',ra,bm,n-4,events['affine_r'],2*n)]:
        add(name,v1,v2,True,fd,event=events['message_factor']*e,
            event_scope='message event and fresh ciphertext randomness',guess=guesses)
    # Both key polynomials have exactly one monomial block. A common signed
    # rotation normalizes f's monomial; at most 2n relative guesses remain.
    vf, vg = af/(4*(1-uf)), ag/(4*(1-ug))
    both = events['affine_f']*events['affine_g']
    add('both_one_monomial_g_first',vg,vf,True,n-4,4,event=both,
        event_scope='accepted keys; rank four branch',guess=2*n)
    rank_loss = (zf/(1-uf)*zg/(1-ug)+af/(1-uf)*ag/(1-ug)/8)**(L-1)
    routes['both_one_monomial_g_first']['rank_loss_given_event'] = probability(rank_loss)
    def best(names):
        key=min(names,key=lambda k:routes[k]['C'])
        return dict(route=key,**routes[key])
    groups={
        'ordinary_key':[k for k in routes if k.startswith(('coefficient_','covariance_')) and k.endswith(('f_g','g_f'))],
        'ordinary_ciphertext':[k for k in routes if k.startswith(('coefficient_','covariance_')) and k.endswith(('r_m','m_r'))],
        'old_conditional':['affine_f','affine_g','affine_r','even_g','even_r'],
        'factored_message':['factor_r_bm_coeff','factor_r_bm_cov','factor_bm_r_cov'],
    }
    return dict(**row,routes=routes,summary={k:best(v) for k,v in groups.items()},
                events={k:probability(v) for k,v in events.items()},
                candidate_search=dict(classical_queries_log2=min(row['mu'],row['nu']),
                                      ideal_quantum_queries_log2=min(row['mu'],row['nu'])/2))


if __name__ == '__main__':
    rows=[profile(row) for row in json.loads((ROOT/'security_inputs.json').read_text())]
    output=dict(model='manuscript GSA feasibility with MATZOV list-decoding port, estimator 5ba00f5',
                convention='C minimized over beta,d; Q evaluated at the same pair',
                scope='modeled reduction work, not measured attack success or certified security',
                rows=rows)
    (ROOT/'security_results.json').write_text(json.dumps(output,indent=2)+'\n')
    for r in rows:
        print(r['profile'])
        for name,rr in r['summary'].items():
            print(name,rr['route'],'C',round(rr['C'],6),'Q',round(rr['Q_at_C'],6),
                  'log2 coverage',round(rr['coverage']['log2'],6))
        for name in ['affine_f','factor_even_r','factor_affine_r','both_one_monomial_g_first']:
            rr=r['routes'][name]
            print(name,'C',round(rr['C'],6),'Q',round(rr['Q_at_C'],6),
                  'coverage',round(rr['coverage']['log2'],6))
