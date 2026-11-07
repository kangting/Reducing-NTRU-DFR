from pathlib import Path
from fractions import Fraction as F
import sys,json
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'deps'))
import correct,route_cost,security
sys.path.insert(0,str(ROOT.parent))
import sharp_correct
CASES=[
 ('S512_q251_C1395_sharp',512,251,256,[(128,39,89),(128,39,89),(128,60,68)],139.5,133.5,166),
 ('S512_q251_C140_sharp',512,251,512,[(247,80,185),(256,71,185),(256,113,143)],140,133.5,166),
 ('S512_q251_C140_simple_sharp',512,251,128,[(63,18,47),(64,17,47),(64,28,36)],140,133.5,166),
 ('S1024_q349_refined',1024,349,256,[(125,21,110),(128,18,110),(128,42,86)],269.9,250.8,163),
]
if __name__=='__main__':
 finite=json.loads((ROOT/'q347_C2699_finite.json').read_text())
 for den in [128,256,512]:
  candidate=next(r for r in finite if r['den']==den)
  CASES.append((f'S1024_q347_den{den}_sharp',1024,347,den,candidate['counts'],269.9,250.8,163))
 rows=[]
 for id,n,q,den,counts,C,Q,b in CASES:
  laws=tuple(tuple(F(x,den)for x in row)for row in counts)+((F(1,4),F(1,2),F(1,4)),)
  cert=correct.exact_certificate(n,q,laws)
  costs={k:route_cost.routes(n,q,laws,k=='quantum')for k in ('classical','quantum')}
  mins={k:c['all_modeled_minimum']for k,c in costs.items()}
  assert mins['classical']['matzov_bits']>=C and mins['quantum']['matzov_bits']>=Q
  row=dict(id=id,n=n,q=q,den=den,counts=counts,laws=laws,targets=dict(C=C,Q=Q,b=b),old_certificate=cert,costs=costs,minima=mins,
    sharp_certificate=sharp_correct.certificate(n,q,laws,b),messages=dict(internal=n//2,external=256,shared_key_output=256))
  rows.append(row)
  assert row['sharp_certificate']['integer_inequality_passes']
  print(id,'C=',mins['classical']['matzov_bits'],'Q=',mins['quantum']['matzov_bits'],
        'old_b=',cert['bound_exponent'],'sharp_b=',row['sharp_certificate']['bound_exponent'],flush=True)
 (ROOT/'selected_refined.json').write_text(json.dumps(rows,default=str,indent=2)+'\n')
