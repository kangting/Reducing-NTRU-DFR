"""Predeclared common controlled-study protocol; exploratory runs are separate."""
CONTROLLED_PROTOCOL = {
    'rounds': 101, 'keygen_count': 1, 'kem_count': 32, 'minimum_accepted': 30,
    'order_seed': 135441, 'warm_keys': 8, 'warm_encaps_decaps': 32,
    'ciphertext_pool': 256, 'counter_read_overhead_pairs': 31,
    'pool_offset_rule': '(round * kem_count) % ciphertext_pool',
    'rejection_rules': ['wrong_cpu', 'involuntary_context_switch', 'major_page_fault', 'multiplexed_or_unscheduled_counter'],
    'voluntary_switches': 'recorded, retained: OS RNG waits are part of KeyGen',
    'clock': 'PERF_COUNT_HW_CPU_CYCLES; raw unscaled per-task user+kernel cycles; wall ns diagnostic only',
}


def validate_protocol(protocol):
    if protocol != CONTROLLED_PROTOCOL:
        changed = sorted(k for k in set(protocol) | set(CONTROLLED_PROTOCOL)
                         if protocol.get(k) != CONTROLLED_PROTOCOL.get(k))
        raise ValueError('Controlled protocol differs from the predeclared study: '+', '.join(changed))
