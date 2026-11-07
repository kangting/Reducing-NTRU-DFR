from pathlib import Path
from fractions import Fraction as F
import sys,json,math,argparse
import numpy as np
ROOT=Path(__file__).resolve().parent;OLD=ROOT.parents[1]/'baseline'
sys.path.insert(0,str(OLD/'profiles/deps'));sys.path.insert(0,str(OLD/'encoding'))
import route_cost,double_correct,double_layer as dl
import pair_mgf
args=argparse.ArgumentParser();args.add_argument('--q',type=int);args=args.parse_args()
rows=json.loads((OLD/'profiles/selected.json').read_text());out=[]
rng=np.random.default_rng(202611071)
for name,q,target,a in [('D512_M128_W_experimental',157,133,F(3)),('D1024_M256_W_experimental',269,163,F(3)),('D1024_M256_W_experimental',251,163,F(5,2))]:
 if args.q and q!=args.q:continue
 old=next(x for x in rows if x['id']==name);n=old['n'];laws=tuple(tuple(F(v)for v in row)for row in old['laws'])
 cost={k:route_cost.routes(n,q,laws,k=='quantum')for k in ('classical','quantum')}
 mins={k:v['all_modeled_minimum']['matzov_bits']for k,v in cost.items()}
 off=double_correct.certificate(n,q,laws,target)
 on=pair_mgf.bound(n,q,laws,a=a,details=True);B=on['bound'];b=math.log2(B.denominator)-math.log2(B.numerator);assert B*2**target<=1
 f,g,h,finv=dl.keygen(n,q,laws[0],laws[1],rng)
 for _ in range(12):
  u=rng.integers(2,size=n//4);c,r,m=dl.encrypt(h,u,laws[2],q,rng);got=dl.decrypt(f,finv,c,q);assert got is not None and np.array_equal(got[0],u)
 poly=((q**n-1).bit_length()+7)//8;M=old['external_message_bits']
 result=dict(id=name+'_correction_on_q'+str(q),n=n,q=q,M=M,u=n//4,K=256,laws=old['laws'],
  minima=mins,costs=cost,off_certificate=off,on_bound_exponent=b,on_target=target,on_target_pass=True,
  on_mgf_base=str(a),on_pass_BAT166_7=(B**10*2**1667<=1),on_bound_numerator_hex=hex(B.numerator),on_bound_denominator_hex=hex(B.denominator),
  on_components={k:float(v)for k,v in on.items()},public_key_bytes=poly,ciphertext_bytes=poly+M//8,total_bytes=2*poly+M//8,
  actual_PKE_roundtrips=12,scope='W-code base-PKE research prototype; no complete KEM safety or constant-time claim')
 out.append(result);print(name,q,'costs',mins,'off b',off['accepted_key_average_zero_wrap_bound_exponent'],'on b',b,'pk/ct/total',poly,poly+M//8,2*poly+M//8,flush=True)
if args.q and (ROOT/'corrected_profiles.json').exists():
 oldout=json.loads((ROOT/'corrected_profiles.json').read_text());out=[x for x in oldout if x['q']!=args.q]+out
(ROOT/'corrected_profiles.json').write_text(json.dumps(out,indent=2,default=str)+'\n')
