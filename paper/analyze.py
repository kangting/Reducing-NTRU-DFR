"""Recompute paper cycle tables from portable scientific raw records."""
from __future__ import annotations
import argparse
import csv
import gzip
import json
import math
from pathlib import Path
import random
import statistics
import specs

HERE = Path(__file__).resolve().parent
OPERATIONS = ('keygen', 'encaps', 'decaps')


def load(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt') as stream:
        return json.load(stream)


def rejection_reasons(batch, cpu):
    reasons = []
    if batch['cpu_start'] != cpu or batch['cpu_end'] != cpu:
        reasons.append('wrong_cpu')
    if batch['involuntary_context_switches']:
        reasons.append('involuntary_context_switch')
    if batch['major_faults']:
        reasons.append('major_page_fault')
    start, end = batch['counter_start'], batch['counter_end']
    if (len(start) != 3 or len(end) != 3
            or any(type(x) is not int or x < 0 for x in start+end)
            or any(y < x for x, y in zip(start, end))):
        raise ValueError('Invalid raw PMU endpoints')
    cycles, enabled, running = [y-x for x, y in zip(start, end)]
    count = batch['count']
    if type(count) is not int or count <= 0 or cycles <= 0 or batch['elapsed_cycles'] != cycles:
        raise ValueError('Raw cycle delta or operation count differs')
    if not math.isclose(batch['cycles_per_operation'], cycles/count, rel_tol=0, abs_tol=1e-6):
        raise ValueError('Cycles per operation differs from raw delta/count')
    if enabled != running or running <= 0:
        reasons.append('multiplexed_or_unscheduled_counter')
    if batch['operation'] != 'keygen' and (batch['rng_calls'] or batch['rng_bytes']):
        raise ValueError('Seeded KEM unexpectedly requested OS entropy')
    if batch['operation'] == 'keygen' and not batch['rng_bytes']:
        raise ValueError('KeyGen OS entropy request is missing')
    return reasons


def summarize(records, targets, minimum):
    result = {}
    bootstrap = random.Random(0x211512)
    for target in targets:
        result[target] = {}
        for operation in OPERATIONS:
            batches = [b for record in records if record['target'] == target
                       for b in record['result']['batches'] if b['operation'] == operation]
            values = sorted(b['cycles_per_operation'] for b in batches if b['accepted'])
            row = dict(accepted_batches=len(values), rejected_batches=len(batches)-len(values),
                       minimum_met=len(values) >= minimum, unit='CPU cycles')
            if values:
                row.update(median=statistics.median(values), minimum=min(values), maximum=max(values))
            if len(values) >= minimum:
                samples = sorted(statistics.median(bootstrap.choices(values, k=len(values))) for _ in range(10000))
                row['median_bootstrap_95_interval'] = [samples[249], samples[9749]]
            result[target][operation] = row
    return result


def validate(data, compare_summary=True):
    if data.get('schema') != 'cntru-paper-cycles-v1' or data.get('status') != 'passed':
        raise ValueError('Expected completed scientific CPU-cycle records')
    protocol = data['protocol']
    expected_protocol = dict(rounds=101, keygen_count=1, kem_count=32, minimum_accepted=30,
                             order_seed=135441, warm_keys=8, warm_encaps_decaps=32,
                             ciphertext_pool=256, counter_read_overhead_pairs=31)
    if any(protocol.get(key) != value for key, value in expected_protocol.items()):
        raise ValueError('Protocol differs from the paper study')
    counter = dict(type='PERF_TYPE_HARDWARE', config='PERF_COUNT_HW_CPU_CYCLES',
                   inherit=False, pinned=True, exclude_user=False,
                   exclude_kernel=False, exclude_hv=True, unit='CPU cycles')
    if (any(data['counter'].get(key) != value for key,value in counter.items())
            or not data['environment']['settings_restored']):
        raise ValueError('Counter or restoration contract differs')
    study = data['study']
    canonical = [specs.canonical(label,study) for label in data['targets']]
    if canonical != specs.cohort(study):
        raise ValueError('Target cohort differs from the paper study')
    if {specs.canonical(label,study) for label in data['excluded']} != specs.exclusions(study):
        raise ValueError('Excluded cohort differs from the paper study')
    for label,descriptor in data['targets'].items():specs.validate_descriptor(label,descriptor,study)
    included = [t for t, p in data['preflight'].items() if p['returncode'] == 0]
    if set(data['targets']) != set(data['preflight']):
        raise ValueError('Incomplete correctness preflight')
    if set(data['excluded']) != set(data['targets'])-set(included):
        raise ValueError('Exclusions contradict preflight')
    for label in data['excluded']:
        if (data['preflight'][label]['returncode'] != 2
                or 'shared-key' not in data['excluded'][label].lower()
                or 'no timing is ranked' not in data['excluded'][label].lower()):
            raise ValueError('Incorrect exclusion reason/status')
    order_rng = random.Random(protocol['order_seed'])
    expected = []
    for number in range(protocol['rounds']):
        order = included.copy()
        order_rng.shuffle(order)
        expected.extend((target, number, order) for target in order)
    if [(r['target'], r['round'], r['order']) for r in data['records']] != expected:
        raise ValueError('Missing, duplicate or reordered measurement record')
    for record in data['records']:
        result = record['result']
        specs.validate_result(result,record['target'],study)
        if (record['returncode'] != 0 or result['clock'] != 'PERF_COUNT_HW_CPU_CYCLES'
                or result['pool'] != 256 or result['keys'] != 8
                or result['correctness_roundtrips'] != 256
                or result['pool_offset'] != (record['round']*32) % 256):
            raise ValueError('Workload or correctness coverage differs')
        overhead = result['counter_read_overhead_cycles']
        if len(overhead) != 31 or any(type(x) is not int or x < 0 for x in overhead):
            raise ValueError('Missing counter-read overhead samples')
        rotation = record['round'] % 3
        if [b['operation'] for b in result['batches']] != list(OPERATIONS[rotation:]+OPERATIONS[:rotation]):
            raise ValueError('Operation order differs')
        for batch in result['batches']:
            count = 1 if batch['operation'] == 'keygen' else 32
            if batch['count'] != count:
                raise ValueError('Batch work count differs')
            reasons = rejection_reasons(batch, data['environment']['cpu'])
            if reasons != batch['rejection_reasons'] or batch['accepted'] != (not reasons):
                raise ValueError('Batch selection differs from the fixed noise rules')
    summary = summarize(data['records'], included, protocol['minimum_accepted'])
    if not all(row['minimum_met'] for group in summary.values() for row in group.values()):
        raise ValueError('Too few accepted batches')
    if compare_summary and summary != data['summary']:
        raise ValueError('Stored summary differs from raw-batch recomputation')
    return summary


def summary_rows(data, summary):
    for target in data['targets']:
        for operation in OPERATIONS:
            row = dict(study=data['study'], target=target, operation=operation,
                       isa=data['targets'][target]['isa'], status='measured', exclusion_reason='',
                       median_kcycles='', ci95_low_kcycles='', ci95_high_kcycles='',
                       accepted_batches='', rejected_batches='')
            if target in data['excluded']:
                row.update(status='excluded', exclusion_reason=data['excluded'][target])
            else:
                metric = summary[target][operation]
                low, high = metric['median_bootstrap_95_interval']
                row.update(median_kcycles=metric['median']/1000,
                           ci95_low_kcycles=low/1000, ci95_high_kcycles=high/1000,
                           accepted_batches=metric['accepted_batches'], rejected_batches=metric['rejected_batches'])
            yield row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', nargs='*', type=Path)
    parser.add_argument('--out', type=Path, default=HERE/'data/cycles-summary.csv')
    args = parser.parse_args()
    paths = args.inputs or [HERE/'data'/f'{name}-raw.json.gz' for name in ('q211', 'levels', 'family')]
    rows = []
    for path in paths:
        data = load(path)
        summary = validate(data)
        rows.extend(summary_rows(data, summary))
        print(f"{data['study']}: {len(data['records'])} processes, {len(summary)*3} operation groups verified")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    print(args.out)


if __name__ == '__main__':
    main()
