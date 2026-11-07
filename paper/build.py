"""Fresh matched C builds; no archived binaries, audit manifests or nested Git.

Builds only unless --test and/or --check is explicit. Runtime build.json files
are ignored local descriptors used by the scoped PMU runner, not paper data.
"""
from __future__ import annotations
import argparse
import copy
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
HERE=ROOT/'paper'
BAT_FILES='api_128_256 api_257_512 api_769_1024 codec fft fnr kem128 kem257 kem769 keygen modqp prng blake2b blake2s'.split()
END_FILES='big_integer fixed_point keygen code module_p ntru pke poly fips202 kem'.split()
SUITES=('family','q211','levels','peers')

def relative(path):return str(Path(path).relative_to(ROOT))
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def specs():
    result={}
    def add(target,suite,n,q,pk,ct,message,source_dir,adapter,definitions=(),test=None,**extra):
        variant=target.rsplit('-',1)[1]
        isa='x86-64' if variant=='ref' else 'x86-64-v3'
        dest=(ROOT/'family_20261107/build'/target.replace('-ref','-portable') if suite=='family' else HERE/'build'/target)
        result[target]=dict(target=target,suite=suite,kind='peer' if suite=='peers' else 'family' if suite=='family' else 'proposed',
            n=n,q=q,pk_bytes=pk,ct_bytes=ct,message_bytes=message,isa=isa,
            source_dir=source_dir,adapter=adapter,definitions=list(definitions),
            build_dir=relative(dest),metadata=relative(dest/'build.json'),executable=relative(dest/'bench'),
            library=relative(dest/('libcntru_family.so' if suite=='family' else 'libcntru.so')) if test else None,
            test_executable=relative(dest/Path(test).stem) if test else None,test_source=test,
            known_preflight_failure=False,**extra)
    catalog=json.loads((ROOT/'family_20261107/profiles.json').read_text())
    for p in catalog['profiles']:
        s=p['semantic'];sample=(s['n']//4)*p['word_bytes'];message=s['external_message_bits']//8
        for variant in ('ref','avx2'):
            defs=[f'-DCNTRU_FAMILY_PROFILE={p["number"]}']
            if variant=='avx2':defs.append('-DCNTRU_AVX2_NTT')
            add(f'p{p["number"]:02d}-{variant}','family',s['n'],s['q'],p['pk_bytes'],p['ct_bytes'],message,
                'family_20261107/src','family_20261107/bench.c',defs,'family_20261107/tests/test_family.c',
                profile_number=p['number'],profile_id=s['id'],expected_keygen_rng_calls=3,
                expected_keygen_rng_bytes=p['f_trials']*sample+2*sample+message)
    for variant in ('ref','scalar-v3','avx2'):
        add('q211-'+variant,'q211',512,211,495,527,32,'hardened','publication/adapters/proposed.c',
            ['-DCNTRU_AVX2_NTT'] if variant=='avx2' else [],'hardened/test_hardened.c',
            expected_keygen_rng_calls=3,expected_keygen_rng_bytes=65536+512+32)
    for q,pk in ((307,1058),(331,1072),(373,1094)):
        for variant in ('ref','avx2'):
            add(f'q{q}-{variant}','levels',1024,q,pk,pk+32,32,'hardened_levels','levels/adapters/proposed.c',
                [f'-DCNTRU_Q={q}']+(['-DCNTRU_AVX2_NTT'] if variant=='avx2' else []),
                'hardened_levels/test_levels.c',expected_keygen_rng_calls=3,expected_keygen_rng_bytes=131072+1024+32)
    for n in (512,1024):
        for scheme in ('bat','end'):
            variants=('ref','avx2') if scheme=='bat' else ('ref','v3','avx2')
            for variant in variants:
                pk,ct,message=({('bat',512):(521,473,16),('end',512):(514,384,32),
                                ('bat',1024):(1230,1006,32),('end',1024):(1027,832,64)})[(scheme,n)]
                src=('benchmarks/vendor/BAT/src' if scheme=='bat' else
                     f'benchmarks/vendor/END/END KEM/END-{n}/END-{n}-257-{"AVX2" if variant=="avx2" else "C"}')
                add(f'{scheme}{n}-{variant}','peers',n,769 if scheme=='bat' and n==1024 else 257,pk,ct,message,
                    src,f'family_20261107/measurement/adapters/{scheme}{n}.c',
                    ['-DBAT_AVX2'] if scheme=='bat' and variant=='avx2' else [],scheme=scheme.upper(),
                    implementation='author AVX2' if variant=='avx2' else 'author C',
                    historical_shared_key_failure=scheme=='end' and (n==1024 or variant=='avx2'))
                result[f'{scheme}{n}-{variant}']['known_preflight_failure']=scheme=='end' and (n==1024 or variant=='avx2')
    return result

TARGETS=specs()

def canonical(target):
    if target.endswith('-portable'):target=target[:-9]+'-ref'
    aliases={'hardened-portable':'q211-ref','hardened-scalar-v3':'q211-scalar-v3','hardened-avx2':'q211-avx2'}
    # The first legacy alias becomes hardened-ref after portable normalization.
    aliases['hardened-ref']='q211-ref'
    target=aliases.get(target,target)
    if target not in TARGETS:raise ValueError('Unknown target: '+target)
    return target

def get_targets(suites=None):
    if suites is None:suites=SUITES
    if isinstance(suites,str):suites=[suites]
    if 'all' in suites:suites=SUITES
    if set(suites)-set(SUITES):raise ValueError('Unknown suite')
    return [name for name,spec in TARGETS.items() if spec['suite'] in suites]

def get_spec(target):return copy.deepcopy(TARGETS[canonical(target)])

def end512_avx2_copy(source,dest):
    """Only the previously documented inconsistent declarations are repaired."""
    copied=dest/'source';shutil.copytree(source,copied,dirs_exist_ok=True)
    replacements={'pke.h':[('int32_t *w','int16_t *w')],
        'kem.h':[('void END_cca_encrypt(int16_t *h','void END_cca_encrypt(int8_t *h'),
                 ('int END_cca_decrypt(int16_t *h','void END_cca_decrypt(int8_t *h')],
        'kem.c':[('void END_cca_encrypt(int16_t *h','void END_cca_encrypt(int8_t *h'),
                 ('int END_cca_decrypt(int16_t *h','void END_cca_decrypt(int8_t *h')]}
    patch=[]
    for name,changes in replacements.items():
        path=copied/name;before=path.read_text();after=before
        for old,new in changes:
            if after.count(old)!=1:raise RuntimeError('Unexpected END declaration in '+name+': '+old)
            after=after.replace(old,new)
        path.write_text(after)
        patch.extend(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='author/'+name,tofile='build-copy/'+name))
    (dest/'declarations.patch').write_text(''.join(patch))
    return copied

def build(target,compiler,run_test=False,run_check=False):
    info=get_spec(target);dest=ROOT/info['build_dir'];dest.mkdir(parents=True,exist_ok=True)
    source_dir=ROOT/info['source_dir'];adapter=ROOT/info['adapter'];log=[];commands=[]
    flags=['-std=gnu11','-O3','-DNDEBUG','-Wall','-Wextra','-fPIC','-march='+info['isa'],'-mtune=generic']
    definitions=info['definitions'];link_flags=['-Wl,-z,noexecstack']
    if info['kind']=='peer' and info['scheme']=='END' and info['n']==512 and target.endswith('-avx2'):
        source_dir=end512_avx2_copy(source_dir,dest);info['declaration_repair']=relative(dest/'declarations.patch')
    if info['kind']!='peer':
        names=['cntru.c','ct_ntt.c','ct_ntt_avx2.c','ct_radix.c']
        if info['suite']=='family':names.append('double_decode.c')
        sources=[source_dir/name for name in names]
    elif info['scheme']=='BAT':
        sources=[source_dir/(name+'.c') for name in BAT_FILES];link_flags.append('-Wl,--wrap=bat_get_seed')
    else:
        sources=[source_dir/(name+'.c') for name in END_FILES]
        if target.endswith('-avx2') and info['n']==512:
            sources += [source_dir/name for name in ('mq_ntt_12289_25601.c','mq_ntt_257_769.S','mq_poly_inv_ntt_257.c')]
        else:
            sources.append(source_dir/'mq_ntt.c')
            if target.endswith('-avx2'):sources += [source_dir/'make_public.c',source_dir/'mq_ntt_257_769.S']
    include_dirs=[source_dir,adapter.parent]
    if info['kind']=='peer':include_dirs.append(ROOT/'family_20261107/measurement')
    includes=[item for path in include_dirs for item in ('-I',relative(path))]
    def run(command,phase,allowed_failure=False):
        result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
        commands.append(dict(phase=phase,command=command,returncode=result.returncode))
        log.append('$ '+' '.join(command)+'\n'+result.stdout+result.stderr)
        (dest/'build.log').write_text('\n'.join(log))
        if result.returncode and not allowed_failure:raise RuntimeError(target+' '+phase+' failed; inspect '+relative(dest/'build.log'))
        return result
    info.update(status='building',compiler=compiler,flags=flags,link_flags=link_flags)
    try:
        objects=[]
        for source in sources:
            obj=dest/(source.stem+'.o')
            run([compiler,*flags,*definitions,*includes,'-c',relative(source),'-o',relative(obj)],'compile-core')
            objects.append(relative(obj))
        info['core_objects']=objects
        if info['library']:
            run([compiler,'-shared',*objects,'-Wl,-z,noexecstack','-o',info['library']],'link-library')
        adapter_object=dest/'adapter.o'
        run([compiler,*flags,*definitions,*includes,'-c',relative(adapter),'-o',relative(adapter_object)],'compile-adapter')
        run([compiler,*flags,*objects,relative(adapter_object),*link_flags,'-o',info['executable']],'link-benchmark')
        if info['test_source']:
            run([compiler,*flags,*definitions,*includes,info['test_source'],*objects,'-Wl,-z,noexecstack','-o',info['test_executable']],'link-test')
        info.update(status='built',binary_sha256=digest(ROOT/info['executable']),
                    compiler_version=subprocess.check_output([compiler,'--version'],text=True).splitlines()[0])
        if info['library']:info['library_sha256']=digest(ROOT/info['library'])
        if run_test and info['test_executable']:
            result=run([info['test_executable']],'test')
            info['test']=dict(status='passed',returncode=result.returncode)
        elif run_test:info['test']=dict(status='not_applicable',reason='Peer adapter correctness is exercised by --check')
        if run_check:
            result=run([info['executable'],'--check'],'check',allowed_failure=True)
            if result.returncode==0:
                info['check']=dict(status='passed',returncode=0,report=json.loads(result.stdout),historical_failure=info['known_preflight_failure'])
                print(target+' correctness passed',flush=True)
            elif (info['known_preflight_failure'] and result.returncode==2
                  and result.stderr.strip()=='benchmark check failed: shared key'):
                info['check']=dict(status='expected_failure',returncode=result.returncode,reason=result.stderr.strip())
                print(target+' EXPECTED FAILURE: shared-key check; no timing result',flush=True)
            else:
                info['check']=dict(status='unexpected_failure',returncode=result.returncode,stderr=result.stderr)
                raise RuntimeError('Unexpected correctness failure: '+target)
    except BaseException as error:
        info.update(status='failed',error=repr(error));raise
    finally:
        info['commands']=commands
        (dest/'build.json').write_text(json.dumps(info,indent=2)+'\n')
    print(target+' built'+(' / C tests passed' if run_test and info['test_executable'] else ''),flush=True)
    return info

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suites','--suite',nargs='+',choices=(*SUITES,'all'),default=['all'])
    parser.add_argument('--targets',nargs='+',help='Canonical labels or -portable aliases')
    parser.add_argument('--cc',default=os.environ.get('CC','gcc'))
    parser.add_argument('--test',action='store_true',help='Execute own C functional tests')
    parser.add_argument('--check',action='store_true',help='Execute benchmark correctness only; does not read PMU counters')
    parser.add_argument('--list',action='store_true',help='List selected targets without building')
    args=parser.parse_args()
    try:selected=list(dict.fromkeys(canonical(x) for x in args.targets)) if args.targets else get_targets(args.suites)
    except ValueError as error:parser.error(str(error))
    if args.list:
        print('\n'.join(selected));return
    compiler=shutil.which(args.cc)
    if not compiler:parser.error('Compiler not found: '+args.cc)
    for target in selected:build(target,compiler,args.test,args.check)

if __name__=='__main__':main()
