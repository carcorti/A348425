#!/usr/bin/env python3
"""Validate the documentary A348425 witness attachment. Author: Carlo Corti.
Direct SymPy factorization/composition on n; no production-source import.
This checks positive witnesses and indexed correspondence, not negative coverage.
"""
from pathlib import Path
import hashlib
import json
import math
import sympy
ROOT = Path(__file__).resolve().parent.parent

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def derivative(n):
    if n < 2:
        return 0
    return sum(int(e) * (n // int(p)) for p, e in sympy.factorint(n).items())

def main():
    a = ROOT / 'data/a348425.txt'
    b = ROOT / 'data/b348425.txt'
    raw = a.read_bytes()
    if not raw.endswith(b'\n\n') or raw.endswith(b'\n\n\n') or b'\r' in raw:
        raise ValueError('a-file framing')
    rows = [tuple(map(int, line.split())) for line in raw.splitlines()
            if line and not line.startswith(b'#')]
    base = [tuple(map(int, line.split())) for line in b.read_text().splitlines() if line]
    if len(rows) != len(base):
        raise ValueError('canonical indexed witness correspondence')
    for ordinal, (row, pair) in enumerate(zip(rows, base), 1):
        if len(row) != 6:
            raise ValueError('column count')
        i, r, n, x, y, q = row
        if i != ordinal or pair != (i, n) or min(row) < 0:
            raise ValueError('index or value')
        if r*r != n or q*q != y or math.isqrt(n) != r or math.isqrt(y) != q:
            raise ValueError('root identity')
        if derivative(n) != x or derivative(x) != y:
            raise ValueError('direct composed derivative')
    print(json.dumps(dict(author='Carlo Corti', status='PASS', rows=len(rows),
        columns=['i','r','n=a(i)','D(n)','D(D(n))','R'],
        derivative_identities=2*len(rows), square_identities=2*len(rows),
        sympy=sympy.__version__, method='direct factorization and composition on n; no C import',
        completeness='Positive witnesses only; indexed completeness requires the separately checked prefix and sealed-run coverage proof',
        files=[dict(path=str(p.relative_to(ROOT)), sha256=digest(p), bytes=p.stat().st_size)
               for p in [a,b,Path(__file__).resolve()]]), indent=2))

if __name__ == '__main__':
    main()
