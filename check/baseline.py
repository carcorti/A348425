#!/usr/bin/env python3
"""Fixed manuscript-review checks, not an official producer or campaign driver.

Author: Carlo Corti. Prepared with Luna (OpenAI Codex), October 23, 2026.
Usage: python3 baseline.py REVIEWER_C CANONICAL_BFILE
The external C bytes are preserved. Only the fixed intervals below may run.
The direct Python baseline uses full trial division of n and D(n).
"""
from pathlib import Path
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import tempfile
import time


def need(ok, message):
    if not ok:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def derivative(n):
    if n < 2:
        return 0
    original, result, p = n, 0, 2
    while p <= n // p:
        while n % p == 0:
            result += original // p
            n //= p
        p = 3 if p == 2 else p + 2
    if n > 1:
        result += original // n
    return result


def prime_factors(n):
    factors, p = {}, 2
    while p <= n // p:
        while n % p == 0:
            factors[p] = factors.get(p, 0) + 1
            n //= p
        p = 3 if p == 2 else p + 2
    if n > 1:
        factors[n] = factors.get(n, 0) + 1
    return factors


BASES = (2, 325, 9375, 28178, 450775, 9780504, 1795265022)


def word_prime(n):
    if n < 2:
        return False
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n % p == 0:
            return n == p
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2
        s += 1
    for a in BASES:
        a %= n
        if a == 0:
            continue
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False
    return True


def main():
    need(len(sys.argv) == 3, 'exactly reviewer C and canonical b-file required')
    source, bfile = map(Path, sys.argv[1:])
    raw = bfile.read_bytes()
    need(digest(raw) == '6c3b7444180c6e1374b3a0046acc12af9a7525979bb5d2b691eac869f6eb498e', 'frozen b-file')
    need(raw.endswith(b'\n\n') and not raw.endswith(b'\n\n\n'), 'terminal empty record')
    rows = [tuple(map(int, line.split())) for line in raw.splitlines() if line]
    need([i for i, _ in rows] == list(range(1, 9115)), 'index continuity')
    roots = [math.isqrt(n) for _, n in rows]
    need(all(r*r == n for r, (_, n) in zip(roots, rows)), 'square inputs')
    source_hash = digest(source.read_bytes())
    # The caller's transport manifest binds the delivered external source hash.
    need(source_hash == '1291f189df023e8084d0b1ba964f8efce739736c81d9e0fe28cfca260d306bae', 'unmodified external C identity')
    started = time.perf_counter()
    direct = []
    for r in range(6501):
        y = derivative(derivative(r*r))
        if math.isqrt(y)**2 == y:
            direct.append(r)
    need(direct == [r for r in roots if r <= 6500], 'complete direct trial baseline')
    need(len(direct) == 35 and direct[:33][-1] == 5623, '33+2 historical prefix')
    windows = ((0, 6500), (1005943, 1006071),
               (5454971392, 5454971520), (9997400103, 9997400231))
    receipts = []
    with tempfile.TemporaryDirectory(prefix='a348425-review-') as td:
        executable = Path(td)/'indep'
        cmd = ['gcc', '-O2', '-std=c17', '-fopenmp', str(source.resolve()), '-lm', '-o', str(executable)]
        built = subprocess.run(cmd, text=True, capture_output=True, timeout=30)
        need(built.returncode == 0, 'support build: '+built.stderr)
        for lo, hi in windows:
            result = subprocess.run([str(executable), str(lo), str(hi)],
                                    env=dict(os.environ, OMP_NUM_THREADS='2'),
                                    text=True, capture_output=True, timeout=30)
            need(result.returncode == 0 and not result.stderr, 'bounded support execution')
            hits = [int(line) for line in result.stdout.splitlines()]
            expected = [r for r in roots if lo <= r <= hi]
            need(hits == expected, 'complete fixed window equality')
            receipts.append(dict(low=lo, high=hi, roots=hi-lo+1, hits=hits))
    # Skipping a zero MR base can only affect a candidate dividing that base.
    exceptional = set()
    for a in BASES:
        divisors = [1]
        for p, e in prime_factors(a).items():
            divisors = [d*p**j for d in divisors for j in range(e+1)]
        exceptional.update(n for n in divisors if n > 1 and sum(prime_factors(n).values()) > 1)
    need(all(not word_prime(n) for n in exceptional), 'all composite zero-base exceptions rejected')
    survivors = sorted(n for n in exceptional if all(n % p for p in (2,3,5,7,11,13,17,19,23,29,31,37)))
    need(survivors == [14089], 'zero-base small-screen residual')
    print(json.dumps(dict(author='Carlo Corti', status='PASS', date='2026-10-23',
        scope='Independent baseline and fixed windows only; no global campaign rerun',
        python=platform.python_version(), source_sha256=source_hash,
        bfile_sha256=digest(raw), direct_trial_baseline_roots=6501,
        direct_trial_baseline_hits=direct, c_windows=receipts,
        composite_zero_base_divisors=len(exceptional), small_screen_survivors=survivors,
        elapsed_seconds=time.perf_counter()-started), indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        raise SystemExit('FAIL: '+str(exc))
