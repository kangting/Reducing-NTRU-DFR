"""Run a fresh controlled cohort using the paper C drivers and real PMU cycles."""
from __future__ import annotations
import argparse
import gzip
import json
import os
from pathlib import Path
import platform
import random
import subprocess

import analyze
import build
from environment import validate_smt_topology
from perf_counter import run_benchmark, COUNTER
from protocol import CONTROLLED_PROTOCOL
from specs import cohort, validate_descriptor, validate_result, exclusions

HERE = Path(__file__).resolve().parent
REPO = HERE.parent


def built_targets(study):
    metadata = {}
    for base in (HERE/'build', REPO/'family_20261107/build'):
        for path in base.glob('*/build.json'):
            row = json.loads(path.read_text())
            metadata[row['target']] = row
    labels = cohort(study)
    if any(t not in metadata for t in labels):
        raise ValueError('Build the requested suite and peers with paper/build.py first')
    selected = {t:metadata[t] for t in labels}
    for label,descriptor in selected.items():validate_descriptor(label,descriptor,study)
    return selected


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    with temporary.open('wb') as stream:
        with gzip.GzipFile(fileobj=stream, mode='wb', mtime=0) as compressed:
            compressed.write(json.dumps(data, separators=(',',':')).encode())
    temporary.replace(path)


def controls(cpu):
    path = os.environ.get('CNTRU_CONTROLLED_ENVIRONMENT')
    if not path:
        raise ValueError('Use paper/run_controlled.sh for timing; direct --check needs no sudo')
    state = json.loads(Path(path).read_text())
    base = Path(f'/sys/devices/system/cpu/cpu{cpu}')
    if state['status'] != 'running' or state['cpu'] != cpu or sorted(os.sched_getaffinity(0)) != [cpu]:
        raise ValueError('Controller or CPU affinity differs from the requested study')
    live = {key:Path(name).read_text().strip() for key,name in state['paths'].items()}
    if live != state['requested'] or state['applied'] != state['requested']:
        raise ValueError('Live CPU controls differ')
    expected = {'scaling_governor':'performance','scaling_min_freq':str(state['frequency_khz']),
                'scaling_max_freq':str(state['frequency_khz'])}
    if any((base/'cpufreq'/key).read_text().strip() != value for key,value in expected.items()):
        raise ValueError('Direct frequency/governor readback differs')
    if Path('/sys/devices/system/cpu/intel_pstate/no_turbo').read_text().strip() != '1':
        raise ValueError('Turbo is enabled')
    validate_smt_topology(cpu,state['thread_siblings_before'],state['siblings'],
                          (base/'topology/thread_siblings_list').read_text().strip(),
                          {str(s):Path(f'/sys/devices/system/cpu/cpu{s}/online').read_text().strip() for s in state['siblings']})
    return state


def preflight(targets, study):
    checked, excluded = {}, {}
    for name, row in targets.items():
        process = subprocess.run([str(REPO/row['executable']),'--check'],text=True,capture_output=True,timeout=180)
        reason = 'correctness checks passed'
        if process.returncode:
            if (not row.get('known_preflight_failure') or process.returncode != 2
                    or process.stderr.strip() != 'benchmark check failed: shared key'):
                raise ValueError(name+': '+process.stderr.strip())
            reason = 'Shared-key preflight failed through the preserved-source adapter; no timing is ranked'
            excluded[name] = reason
        else:
            validate_result(json.loads(process.stdout),name,study,preflight=True)
        checked[name] = {'returncode':process.returncode,'reason':reason}
        print(name+': '+reason,flush=True)
    if set(excluded) != exclusions(study):
        raise ValueError('Preflight membership changed; review the study cohort before timing')
    return checked, excluded


def finalize(path, environment):
    data = analyze.load(path)
    state = json.loads(Path(environment).read_text())
    if (data['status'] != 'passed' or state['status'] != 'completed'
            or state['benchmark_returncode'] != 0 or not state['restoration_verified']
            or state['restored'] != state['original'] or state['restoration_errors']):
        raise ValueError('Controller completion/restoration is not verified')
    if any(Path(name).read_text().strip() != state['original'][key] for key,name in state['paths'].items()):
        raise ValueError('Post-run CPU readback differs from original settings')
    data['environment']['settings_restored'] = True
    analyze.validate(data)
    save(path,data)
    print('Controlled run and CPU restoration verified:',path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study',choices=('q211','levels','family'),default='family')
    parser.add_argument('--cpu',type=int,default=4)
    parser.add_argument('--out',type=Path)
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--finalize-environment',type=Path)
    args = parser.parse_args()
    if args.finalize_environment:
        if args.out is None:parser.error('--out is required')
        finalize(args.out,args.finalize_environment)
        return
    if os.geteuid() == 0:parser.error('Run as the ordinary user')
    targets = built_targets(args.study)
    if args.check:
        preflight(targets,args.study)
        return
    if args.out is None:parser.error('--out is required')
    if not str(args.out).endswith('.json.gz'):parser.error('--out must end with .json.gz')
    journal = args.out.with_suffix('.records.jsonl')
    if args.out.exists() or journal.exists():parser.error('Choose a fresh output name')
    os.sched_setaffinity(0,{args.cpu})
    state = controls(args.cpu)
    scientific_fields = ('target','kind','profile_number','profile_id','isa','flags','definitions',
                         'n','q','pk_bytes','ct_bytes','message_bytes','expected_keygen_rng_calls',
                         'expected_keygen_rng_bytes')
    scientific_targets = {name:{key:row[key] for key in scientific_fields if key in row}
                          for name,row in targets.items()}
    data = {'schema':'cntru-paper-cycles-v1','study':args.study,'status':'running',
            'protocol':CONTROLLED_PROTOCOL,'counter':COUNTER,'targets':scientific_targets,'records':[],
            'environment':{'cpu_model':next(line.split(':',1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')),
                           'kernel':platform.release(),'architecture':platform.machine(),
                           'compiler':next(iter(targets.values()))['compiler_version'],
                           'cpu':args.cpu,'frequency_khz':state['frequency_khz'],
                           'smt_siblings_disabled':state['siblings'],'requested_controls':state['requested'],
                           'settings_restored':False}}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    try:
        data['preflight'],data['excluded'] = preflight(targets,args.study)
        included = [t for t,p in data['preflight'].items() if p['returncode'] == 0]
        order_rng = random.Random(CONTROLLED_PROTOCOL['order_seed'])
        with journal.open('x') as raw:
            for number in range(CONTROLLED_PROTOCOL['rounds']):
                order = included.copy();order_rng.shuffle(order)
                for name in order:
                    controls(args.cpu)
                    command = [str(REPO/targets[name]['executable']),'1','32',str(number%3),str((number*32)%256)]
                    process = run_benchmark(command,capture_output=True,text=True,timeout=180)
                    record = {'target':name,'round':number,'order':order,'returncode':process.returncode}
                    raw.write(json.dumps({**record,'stdout':process.stdout,'stderr':process.stderr})+'\n')
                    raw.flush();os.fsync(raw.fileno())
                    if process.returncode:raise ValueError(name+': '+process.stderr.strip())
                    record['result'] = json.loads(process.stdout)
                    data['records'].append(record)
                    validate_result(record['result'],name,args.study)
                    controls(args.cpu)
                    for batch in record['result']['batches']:
                        reasons = analyze.rejection_reasons(batch,args.cpu)
                        batch.update(rejection_reasons=reasons,accepted=not reasons)
                save(args.out,data)
                print(f'completed round {number+1}/101',flush=True)
        data['summary'] = analyze.summarize(data['records'],included,30)
        if not all(row['minimum_met'] for group in data['summary'].values() for row in group.values()):
            raise ValueError('Insufficient accepted batches; preserve the failed run')
        data['status'] = 'passed'
    except BaseException as error:
        data['status'] = 'failed';data['error'] = repr(error)
        raise
    finally:
        save(args.out,data)


if __name__ == '__main__':
    main()
