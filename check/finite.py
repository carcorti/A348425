#!/usr/bin/env python3
"""Sofia's independent checker (Anthropic Claude). No code shared with the C kernel
or with the maintainer's verify.py. D(n) = sum e_p * (n/p) from an explicit
factorization; D(D(r^2)) is computed directly on x = D(r^2) = 2*r*D(r) by
factorizing x as the product 2*r*D(r) (exact multiset merge), NOT via the
production identity y = r d + 2 d^2 + 2 r e.  Usage:
  indep.py dump.tsv hits.txt   (dump from sieve_dump; hits from its stderr)
  indep.py census LOW HIGH     (pure trial-division census, prints hit roots)
"""
import sys, math
from collections import Counter
from sympy import factorint

def fac_trial(n):
    f = Counter(); p = 2
    while p * p <= n:
        while n % p == 0: f[p] += 1; n //= p
        p += 1 if p == 2 else 2
    if n > 1: f[n] += 1
    return f

def D_from(n, f):
    return sum(e * (n // p) for p, e in f.items()) if n > 1 else 0

def fac(n, trial):
    if n < 2: return Counter()
    return fac_trial(n) if trial else Counter({int(p): int(e) for p, e in factorint(n).items()})

def second(r, trial):
    if r < 2: return 0, 0, 0
    fr = fac(r, trial)
    n = r * r
    x = D_from(n, Counter({p: 2 * e for p, e in fr.items()}))
    d = D_from(r, fr)
    assert x == 2 * r * d
    fx = Counter({2: 1}) + fr + fac(d, trial)
    assert math.prod(p ** e for p, e in fx.items()) == x
    y = D_from(x, fx)
    return d, x, y

if sys.argv[1] == 'census':
    lo, hi = int(sys.argv[2]), int(sys.argv[3])
    for r in range(lo, hi + 1):
        d, x, y = second(r, True)
        if math.isqrt(y) ** 2 == y: print(r, r * r, x, y, math.isqrt(y))
    sys.exit(0)

dump, hitfile = sys.argv[1], sys.argv[2]
rows = 0; bad = 0; hits = []
for line in open(dump):
    r, dC, eC = map(int, line.split('\t'))
    d, x, y = second(r, r < 10**7)
    e = D_from(d, fac(d, d < 10**7)) if d > 1 else 0
    rows += 1
    if d != dC or e != eC:
        bad += 1
        if bad < 5: print('MISMATCH', r, dC, d, eC, e)
    assert y == r * d + 2 * d * d + 2 * r * e  # identity holds numerically
    if math.isqrt(y) ** 2 == y: hits.append((r, y, math.isqrt(y)))
chits = [tuple(map(int, l.split()[1:])) for l in open(hitfile) if l.startswith('HIT ')]
print(f'rows={rows} d/e mismatches={bad} python_hits={len(hits)} C_hits={len(chits)} equal={hits == chits}')
for h in hits: print('  hit', h)
sys.exit(0 if bad == 0 and hits == chits else 1)
