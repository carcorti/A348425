#!/usr/bin/env python3
"""Finite analysis of the frozen A348425 documentary table.

Author: Carlo Corti. Prepared with Luna (OpenAI Codex).
This is a manuscript companion, not a producer or a negative-coverage audit.
Only supplied positive rows and their canonical core/rate pairs are examined.
Usage: python3 -B paper/analysis.py data/a348425.txt > outputs/paper/stats.json
The canonical b348425.txt is also accepted; its witness chains are reconstructed.
Requires the recorded SymPy 1.12; no C imports, subprocesses or root search.
"""
import collections
import functools
import hashlib
import json
import math
from pathlib import Path
import sys
import sympy


def require(test, message):
    if not test:
        raise ValueError(message)


@functools.lru_cache(maxsize=None)
def factors(n):
    require(n >= 1, 'positive factorization input')
    f = {int(p): int(e) for p, e in sympy.factorint(n).items()}
    require(all(1 < p < 2**64 and e > 0 and sympy.isprime(p)
                for p, e in f.items()), 'exact word-prime factor leaves')
    require(math.prod(p**e for p, e in f.items()) == n, 'factor product')
    return f


def derivative(n):
    return 0 if n < 2 else sum(e*(n//p) for p, e in factors(n).items())


def main():
    require(sympy.__version__ == '1.12', 'recorded SymPy 1.12 required')
    path = Path(sys.argv[1]) if len(sys.argv) == 2 else Path(__file__).resolve().parents[1]/'data/a348425.txt'
    require(len(sys.argv) <= 2, 'at most one input file')
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    is_bfile = digest == '6c3b7444180c6e1374b3a0046acc12af9a7525979bb5d2b691eac869f6eb498e'
    require(is_bfile or digest ==
            '1656224753e4d41b81ade659b728672bdaad56cbfbaaa4891ea0c26da7880762',
            'frozen 9114-row canonical input identity')
    require(raw.endswith(b'\n\n') and not raw.endswith(b'\n\n\n') and b'\r' not in raw,
            'LF LF framing')
    rows = [tuple(map(int, line.split())) for line in raw.splitlines()
            if line and not line.startswith(b'#')]
    if is_bfile:
        require(all(len(row) == 2 for row in rows), 'b-file columns')
        reconstructed = []
        for i, n in rows:
            r = math.isqrt(n)
            x = derivative(n)
            y = derivative(x)
            reconstructed.append((i, r, n, x, y, math.isqrt(y)))
        rows = reconstructed
    require(len(rows) == 9114, 'complete supplied positive table')
    rates = collections.Counter()
    classes = collections.defaultdict(list)
    powers = collections.defaultdict(list)
    intersections = []
    decades = collections.Counter()
    inherited = {(47, 1), (125, 1), (875, 1), (529, 2)}
    categories = collections.Counter()
    residuals = []
    previous = -1
    max_factor = 0
    for ordinal, row in enumerate(rows, 1):
        require(len(row) == 6, 'six columns')
        i, r, n, x, y, R = row
        require(i == ordinal and min(row) >= 0 and r > previous, 'index/order/domain')
        require(r*r == n and R*R == y, 'two square identities')
        require(derivative(n) == x and derivative(x) == y, 'direct composition')
        d = derivative(r)
        require(x == 2*r*d and y == r*d+2*d*d+2*r*derivative(d), 'root reduction')
        previous = r
        decades[sum(r > 10**j for j in range(0, 11))] += 1
        if math.isqrt(x)**2 == x:
            intersections.append(i)
        if r < 2:
            categories['zero_or_one'] += 1
            continue
        f = factors(r)
        max_factor = max(max_factor, max(f))
        m = math.prod(p**(e % p) for p, e in f.items())
        t = r//m
        rate = sum(e//p for p, e in f.items())
        require(m*t == r and derivative(t) == rate*t, 'canonical decomposition')
        b = derivative(m)+rate*m
        coefficient = 2*derivative(m*b)+(4*rate+1)*m*b
        croot = math.isqrt(coefficient)
        require(coefficient == croot*croot and R == t*croot, 'scale certificate')
        rates[rate] += 1
        classes[m, rate].append((i, r, R))
        if len(f) == 1:
            p, k = next(iter(f.items()))
            bracket = p*derivative(2*k)+2*k*(2*k-1)
            require(y == p**(2*k-2)*bracket and math.isqrt(bracket)**2 == bracket,
                    'prime-power identity')
            powers[k].append((i, p, r))
            categories['prime_root' if k == 1 else 'higher_prime_power_root'] += 1
        else:
            categories['mixed_root'] += 1
        # A disjoint explanation partition: small exponent constructions first.
        if len(f) == 1 and next(iter(f.values())) <= 3:
            categories['explained_k_1_2_3'] += 1
        elif (m, rate) in inherited:
            categories['explained_inherited_four'] += 1
        else:
            residuals.append((i, r, m, rate))
    nonzero = []
    for (m, rate), members in sorted(classes.items()):
        if rate:
            b = derivative(m)+rate*m
            C = 2*derivative(m*b)+(4*rate+1)*m*b
            nonzero.append(dict(m=m, rate=rate, Dm=derivative(m), b=b,
                Dmb=derivative(m*b), coefficient=C, R_over_t=math.isqrt(C),
                count=len(members), first=list(members[0]), last=list(members[-1]),
                inherited=(m, rate) in inherited))
    require(len({q['m'] for q in nonzero}) == len(nonzero), 'distinct reduced cores')
    # Targeted existing witness; it has no assigned sequence index.
    r = 529*7**7*3**3
    x = derivative(r*r)
    y = derivative(x)
    require(y == (2852*7**7*3**3)**2, 'unindexed upper witness')
    # Adjacent evidence from A028871(8889), also in the pre-existing family list.
    # Check this one root by complete trial division, not a new family search.
    adjacent = 10009802399
    trial_divisors = [2] + list(range(3, math.isqrt(adjacent)+1, 2))
    require(all(adjacent % p for p in trial_divisors), 'adjacent witness prime')
    require(adjacent+2 == 100049**2, 'adjacent prime-shape identity')
    # Literal parameter counterexample from the historical OEIS comment.
    require(5*599**2-6 == 19*94421, 'comment parameter counterexample')
    result = dict(author='Carlo Corti', status='PASS', sympy=sympy.__version__,
        input_sha256=hashlib.sha256(raw).hexdigest(), rows=len(rows),
        scope='Supplied positive data only; no enumeration of missing roots or new seeds',
        direct_derivative_identities=2*len(rows), square_identities=2*len(rows),
        categories=dict(categories), canonical_rates=dict(sorted(rates.items())),
        prime_power_exponents={str(k): dict(count=len(v), examples=v[:4])
                               for k, v in sorted(powers.items())},
        classes_nonzero_rate=nonzero, distinct_core_rate_classes=len(classes),
        first_derivative_square_indices=intersections,
        residual_after_three_constructions_and_four_families=dict(count=len(residuals),
            nonzero_rate=sum(rate > 0 for i, r, m, rate in residuals),
            zero_rate=sum(rate == 0 for i, r, m, rate in residuals), examples=residuals[:10]),
        upper_witness=dict(r=r, n=r*r, Dn=x, DDn=y, R=math.isqrt(y), indexed=False),
        sharper_upper_witness=dict(r=adjacent, n=adjacent**2, Dn=2*adjacent,
            DDn=adjacent+2, R=100049, indexed=False,
            prime_proof='complete trial division', trial_divisors=len(trial_divisors)),
        counts_at_root_caps={str(cap):sum(row[1] <= cap for row in rows)
                            for cap in [6500,10**6,10**7,10**8,10**9,10**10]},
        max_root_prime_factor=max_factor)
    print(json.dumps(result, indent=2)+'\n', end='')


if __name__ == '__main__':
    main()
