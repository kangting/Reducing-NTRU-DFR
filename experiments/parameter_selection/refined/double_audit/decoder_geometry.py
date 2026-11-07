"""Exhaustive synthetic-noise containment check at n8,q3, f=1."""
from pathlib import Path
from itertools import product,islice
import json,sys
import numpy as np
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parents[1]/'baseline/encoding'))
import double_layer as dl

n=8;L=2;q=3;t=2
source=product(range(-2,3),repeat=n)
counts=dict(total=0,valid_codeword_noise=0,decoder_failures=0,failures_outside_bound_events=0,actual_decoder_crosschecks=0)
while True:
    vals=list(islice(source,16384))
    if not vals:break
    z=np.asarray(vals,dtype=np.int64);counts['total']+=len(z)
    residue=(z[:,:4]+z[:,4:])%2
    valid=np.all(residue[:,:2]==residue[:,2:],axis=1)
    z=z[valid];expected=residue[valid,:2]
    counts['valid_codeword_noise']+=len(z)
    v=(z+q//2)%q-q//2;bits=v%2
    syndrome=bits.reshape(-1,4,L).sum(axis=1)%2
    flips=syndrome.sum(axis=1);rejected=flips>1
    for row in np.flatnonzero(flips==1):
        i=int(np.flatnonzero(syndrome[row])[0]);positions=np.arange(i,n,L)
        j=int(positions[np.argmax(np.abs(v[row,positions]))]);bits[row,j]^=1
    out=(bits[:,:4]+bits[:,4:])%2
    rejected|=np.any(out[:,:2]!=out[:,2:],axis=1)
    failed=rejected|np.any(out[:,:2]!=expected,axis=1)
    counts['decoder_failures']+=int(failed.sum())
    absz=np.abs(z)
    two=(absz>=t).sum(axis=1)>=2
    extreme=np.any(absz>=q,axis=1)
    quart=np.sort(absz.reshape(-1,4,L),axis=1)
    within=np.any(quart[:,-1,:]+quart[:,-2,:]>=q,axis=1)
    outside=failed&~(two|extreme|within)
    counts['failures_outside_bound_events']+=int(outside.sum())
    assert not np.any(outside)
    for i in range(min(16,len(v))):
        actual=dl.decode_v(v[i],1)
        afail=actual is None or not np.array_equal(actual[0],expected[i])
        assert afail==bool(failed[i])
        counts['actual_decoder_crosschecks']+=1
counts['containment_passed']=True
(ROOT/'decoder_geometry.json').write_text(json.dumps(counts,indent=2)+'\n')
print(counts)
