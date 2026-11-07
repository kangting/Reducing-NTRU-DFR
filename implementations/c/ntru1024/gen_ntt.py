#!/usr/bin/env python3
"""Reproduce/check the exact public2048-root tables and arithmetic bounds."""
import argparse
import json
from math import isqrt
from pathlib import Path


def require(value,message):
    if not value:raise ValueError(message)


def generate():
    bound=1024*186**2
    modulus_product=12289*18433
    require(modulus_product==226523137 and modulus_product>2*bound,'centered CRT bound')
    require(pow(12289,-1,18433)==3,'CRT inverse')
    report={'maximum_n':1024,'maximum_transform_length':2048,
            'original_helper_input_bound':372,'centered_input_bound':186,
            'maximum_absolute_centered_coefficient':bound,
            'crt_modulus':modulus_product,'crt_inverse':3,'primes':[]}
    result={};ntt16=''
    for prime,g,name in ((998244353,3,'ntt'),(12289,11,'ntt16_0'),(18433,5,'ntt16_1')):
        require(all(prime%d for d in range(2,isqrt(prime)+1)),f'composite modulus {prime}')
        require((prime-1)%2048==0,'missing2048th roots')
        bits=32 if name=='ntt' else 16;r=pow(2,bits,prime)
        if bits==16:
            require(2*prime<65536 and prime<32768,'unsigned sum/signed corrected difference range')
            require(prime+(prime*prime//65536)+1<32768,'16-bit Montgomery accumulator range')
        else:require(prime>2*bound,'scalar centered lift bound')
        report['primes'].append({'p':prime,'generator':g,'montgomery_bits':bits,
                                'negative_inverse':-pow(prime,-1,1<<bits)%(1<<bits),
                                'r2':r*r%prime,'root2048':pow(g,(prime-1)//2048,prime)})
        content=['/* Checked public2048-root Montgomery tables. */','#include <stdint.h>']
        for inverse in (False,True):
            values=[0]*2048
            for k in range(1,12):
                half=1<<(k-1);omega=pow(g,(prime-1)//(2*half),prime)
                require(pow(omega,half,prime)==prime-1 and pow(omega,2*half,prime)==1,'incorrect root order')
                if inverse:omega=pow(omega,-1,prime)
                w=1
                for j in range(half):values[half+j]=w*r%prime;w=w*omega%prime
            var=name+('_inverse_twiddles' if inverse else '_forward_twiddles') if name=='ntt' else name+('_inverse' if inverse else '_forward')
            content.append(('_Alignas(32) ' if bits==16 else '')+f'static const uint{bits}_t {var}[2048] = {{')
            content.extend('    '+','.join(map(str,values[j:j+16]))+',' for j in range(0,2048,16));content.append('};')
            if bits==16:
                content.append(f'_Alignas(32) static const uint16_t {var}_small[4][16] = {{')
                for k in range(4):
                    half=1<<k
                    row=[values[half+(lane&(half-1))] if not inverse or lane&half else r for lane in range(16)]
                    content.append('    {'+','.join(map(str,row))+'},')
                content.append('};')
        content.append(f'static const uint{bits}_t {name}_inverse_lengths[12] = '+'{'+','.join(str(pow(1<<k,-1,prime)*r%prime) for k in range(12))+'};')
        if name=='ntt':result['ntt_tables.h']='\n'.join(content)+'\n'
        else:ntt16+='\n'.join(content)+'\n'
    ntt16+='_Alignas(32) static const uint16_t ntt16_upper_masks[4][16] = {\n'
    for k in range(4):ntt16+='    {'+','.join(str(65535 if lane&(1<<k) else 0) for lane in range(16))+'},\n'
    result['ntt16_tables.h']=ntt16+'};\n'
    result['ntt_contract.json']=json.dumps(report,indent=2)+'\n'
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true')
    args=parser.parse_args();root=Path(__file__).resolve().parent
    for name,text in generate().items():
        path=root/name
        if args.check:require(path.is_file() and path.read_text()==text,'generated NTT file mismatch: '+name)
        else:path.write_text(text)
    print('PASS: exact2048 roots, prime moduli, centered lift/CRT and Montgomery ranges')
