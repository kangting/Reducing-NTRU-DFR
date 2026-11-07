"""Canonical study membership and wire/RNG contracts shared by live/offline tools."""
import build


def cohort(study):
    if study == 'family':
        return [f'p{i:02d}-{isa}' for i in range(1,17) for isa in ('ref','avx2')]+[
            f'{scheme}{n}-{isa}' for n in (512,1024) for scheme in ('bat','end') for isa in ('ref','avx2')]
    if study == 'q211':
        return ['q211-ref','q211-scalar-v3','q211-avx2','bat512-ref','bat512-avx2',
                'end512-ref','end512-v3','end512-avx2']
    if study == 'levels':
        return [f'q{q}-{isa}' for q in (307,331,373) for isa in ('ref','avx2')]+[
            'bat1024-ref','bat1024-avx2','end1024-ref','end1024-v3','end1024-avx2']
    raise ValueError('Unknown study')


def canonical(label, study):
    if study == 'q211':
        aliases = {'bat-portable':'bat512-ref','bat-avx2':'bat512-avx2',
                   'end-portable':'end512-ref','end-v3':'end512-v3','end-avx2':'end512-avx2'}
        label = aliases.get(label,label)
    return build.canonical(label)


def spec(label, study):
    return build.get_spec(canonical(label,study))


def exclusions(study):
    return {label for label in cohort(study) if build.get_spec(label)['known_preflight_failure']}


def validate_descriptor(label, descriptor, study):
    expected = spec(label,study)
    fields = ['n','q','pk_bytes','ct_bytes','message_bytes','isa']
    if expected['kind'] == 'family':fields += ['profile_number','profile_id']
    if any(descriptor.get(key) != expected[key] for key in fields):
        raise ValueError('Target descriptor differs from parameter/ISA catalog: '+label)
    return expected


def validate_result(result, label, study, preflight=False):
    expected = spec(label,study)
    if (result.get('pk_bytes') != expected['pk_bytes'] or result.get('ct_bytes') != expected['ct_bytes']
            or result.get('pool',256) != 256 or result.get('keys') != 8):
        raise ValueError('Result geometry differs from target contract: '+label)
    if 'seed_bytes' in result and result['seed_bytes'] != expected['message_bytes']:
        raise ValueError('External message length differs from target contract: '+label)
    if study != 'q211' and result.get('seed_bytes') != expected['message_bytes']:
        raise ValueError('Missing external message length: '+label)
    if expected['kind'] == 'family':scheme = expected['profile_id']
    elif expected['kind'] == 'proposed':
        scheme = 'Complementary-NTRU-q211' if expected['q']==211 else 'Complementary-NTRU-n1024'
    else:scheme = expected['scheme']+'-'+str(expected['n'])
    if result.get('scheme') != scheme:
        raise ValueError('Result profile differs from target contract: '+label)
    if preflight:
        if result.get('status') != 'passed' or result.get('roundtrips') != 256:
            raise ValueError('Preflight coverage differs from target contract: '+label)
    else:
        for batch in result['batches']:
            if batch['operation'] == 'keygen' and expected['kind'] != 'peer':
                count = batch['count']
                if (batch['rng_calls'] != expected['expected_keygen_rng_calls']*count
                        or batch['rng_bytes'] != expected['expected_keygen_rng_bytes']*count):
                    raise ValueError('KeyGen RNG schedule differs from target contract: '+label)
