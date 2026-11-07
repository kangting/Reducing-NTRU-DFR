"""Arithmetic over Z[x]/(x^512+1) and canonical radix-q encoding."""
import numpy as np

def mul(a, b, q=None):
    n = len(a)
    v = np.convolve(np.asarray(a, dtype=np.int64), np.asarray(b, dtype=np.int64))
    c = np.array(v[:n], dtype=np.int64)
    if len(v) > n:
        c[:len(v) - n] -= v[n:]
    return c if q is None else c % q

def trim(a):
    a = list(a)
    while a and a[-1] == 0:
        a.pop()
    return a

def pdiv(a, b, q):
    a = trim([int(x) % q for x in a])
    b = trim([int(x) % q for x in b])
    if not b:
        raise ZeroDivisionError
    z = [0] * max(0, len(a) - len(b) + 1)
    ib = pow(b[-1], -1, q)
    while len(a) >= len(b):
        i = len(a) - len(b)
        x = a[-1] * ib % q
        z[i] = x
        for j, y in enumerate(b):
            a[i + j] = (a[i + j] - x * y) % q
        a = trim(a)
    return (trim(z), a)

def pmul(a, b, q):
    if not a or not b:
        return []
    c = [0] * (len(a) + len(b) - 1)
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            c[i + j] = (c[i + j] + x * y) % q
    return trim(c)

def psub(a, b, q):
    return trim([((a[i] if i < len(a) else 0) - (b[i] if i < len(b) else 0)) % q for i in range(max(len(a), len(b)))])

def invq(f, q):
    n = len(f)
    r0 = [1] + [0] * (n - 1) + [1]
    r1 = trim([int(x) % q for x in f])
    t0 = []
    t1 = [1]
    while r1:
        h, r = pdiv(r0, r1, q)
        r0, r1 = (r1, r)
        t0, t1 = (t1, psub(t0, pmul(h, t1, q), q))
    if len(r0) != 1:
        return None
    t0 = [x * pow(r0[0], -1, q) % q for x in t0]
    _, t = pdiv(t0, [1] + [0] * (n - 1) + [1], q)
    return np.array(t + [0] * (n - len(t)), dtype=np.int64)

def f2_div(a, b):
    z = 0
    while a and a.bit_length() >= b.bit_length():
        d = a.bit_length() - b.bit_length()
        z ^= 1 << d
        a ^= b << d
    return (z, a)

def f2_mul(a, b):
    z = 0
    while b:
        if b & 1:
            z ^= a
        a <<= 1
        b >>= 1
    return z

def f2_inv(a, k):
    mod = 1 << k | 1
    r0, r1 = (mod, a)
    t0, t1 = (0, 1)
    while r1:
        h, r = f2_div(r0, r1)
        r0, r1 = (r1, r)
        t0, t1 = (t1, t0 ^ f2_mul(h, t1))
    if r0 != 1:
        return None
    return f2_div(t0, mod)[1]

def packbits(a):
    return sum(((int(x) & 1) << i for i, x in enumerate(a)))

def unpackbits(a, k):
    return np.array([a >> i & 1 for i in range(k)], dtype=np.int64)

def residue(a, k):
    # Modulo 1+x^k in characteristic two, fold coefficient groups with XOR.
    return np.sum(np.asarray(a).reshape(-1, k), axis=0) % 2

def f2_ringmul(a, b, k):
    return f2_div(f2_mul(a, b), 1 << k | 1)[1]

def center(a, q):
    return (np.asarray(a) + q // 2) % q - q // 2

def encoded_length(count, radix):
    return ((radix ** count - 1).bit_length() + 7) // 8

def pack(values, radix):
    values = [int(x) for x in values]
    if radix < 2 or any((x < 0 or x >= radix for x in values)):
        raise ValueError('coefficient outside the radix')
    integer = 0
    for x in reversed(values):
        integer = integer * radix + x
    return integer.to_bytes(encoded_length(len(values), radix), 'little')

def unpack(encoded, count, radix):
    if len(encoded) != encoded_length(count, radix):
        raise ValueError('incorrect encoded length')
    integer = int.from_bytes(encoded, 'little')
    if integer >= radix ** count:
        raise ValueError('noncanonical encoding')
    values = []
    for _ in range(count):
        integer, x = divmod(integer, radix)
        values.append(x)
    assert integer == 0
    return np.asarray(values, dtype=np.int64)
