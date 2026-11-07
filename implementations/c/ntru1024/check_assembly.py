#!/usr/bin/env python3
"""Reject hardware/helper integer division in the selected built library."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def main():
    root=Path(__file__).resolve().parents[3]
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,default=root/'benchmarks/build/q307-ref/libcntru.so')
    parser.add_argument('--out',type=Path,default=root/'benchmarks/build/q307-ref/assembly_check.json')
    args=parser.parse_args()
    listing=subprocess.check_output(['objdump','-d','--no-show-raw-insn',str(args.library)],text=True)
    symbols=subprocess.check_output(['nm','-D',str(args.library)],text=True)
    divisions=[]
    branches={}
    function=''
    for line in listing.splitlines():
        match=re.match(r'^[0-9a-f]+ <([^>]+)>:',line)
        if match:function=match.group(1)
        instruction=re.match(r'^\s*([0-9a-f]+):\s+([a-z][a-z0-9]*)\b',line)
        if not instruction:continue
        address,mnemonic=instruction.groups()
        if re.fullmatch(r'i?div[bwlq]?',mnemonic):
            divisions.append({'function':function,'address':address,'instruction':line.strip()})
        if mnemonic.startswith('j') and mnemonic not in ('jmp','jmpq'):
            branches.setdefault(function,[]).append({'address':address,'mnemonic':mnemonic})
    helpers=[line for line in symbols.splitlines() if re.search(r'\b__(?:u?div|u?mod|udivmod)',line)]
    out={'library':str(args.library.resolve()),'sha256':hashlib.sha256(args.library.read_bytes()).hexdigest(),
         'hardware_divisions':divisions,'division_helpers':helpers,'conditional_branches':branches,
         'division_check_passed':not divisions and not helpers,
         'scope':'Division-instruction/helper check only; branch lists require public/secret dataflow review. Not a constant-time proof.'}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(out,indent=2)+'\n')
    args.out.with_suffix('.asm').write_text(listing)
    print(json.dumps({'division_check_passed':out['division_check_passed'],
                      'division_count':len(divisions),'helper_count':len(helpers),'report':str(args.out)}))
    raise SystemExit(0 if out['division_check_passed'] else 1)


if __name__=='__main__':main()
