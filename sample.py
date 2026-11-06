"""Sample finite block laws from uniform bytes using integer tables."""
import bisect
import math
from fractions import Fraction

import numpy as np


class Table:
    def __init__(self, rows):
        probabilities = [Fraction(row['numerator'], row['denominator']) for row in rows]
        denominator = math.lcm(*(p.denominator for p in probabilities))
        weights = [p.numerator * (denominator // p.denominator) for p in probabilities]
        divisor = math.gcd(*weights)
        weights = [w // divisor for w in weights]
        self.atoms = np.array([row['atom'] for row in rows], dtype=np.int64)
        self.cdf = []
        total = 0
        for weight in weights:
            total += weight
            self.cdf.append(total)
        self.total = total
        self.bits = (total - 1).bit_length()
        self.bytes = (self.bits + 7) // 8
        self.mask = (1 << self.bits) - 1

    def sample(self, source):
        # Every table in par.json, including each conditional message class,
        # has power-of-two total weight and therefore needs no rejection.
        while True:
            index = int.from_bytes(source(self.bytes), 'little') & self.mask
            if index < self.total:
                return self.atoms[bisect.bisect_right(self.cdf, index)]
