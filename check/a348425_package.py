#!/usr/bin/env python3
"""Bounded public reproduction of the A348425 manuscript and frozen evidence.

Author: Carlo Corti. Prepared with Luna (OpenAI Codex).
Run: python3 -I -B check/a348425_package.py
No init/next, full campaign, installation, network or PDF generation.
All builds and archive restoration occur in disposable directories.
"""
from pathlib import Path, PurePosixPath
import gzip
import hashlib
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def safe_name(name):
    p = PurePosixPath(name)
    return (bool(name) and not p.is_absolute() and '..' not in p.parts
            and '\\' not in name and str(p) == name)


def inventory():
    actual = set()
    for path in ROOT.rglob('*'):
        rel = path.relative_to(ROOT)
        if rel.parts[0] == '.git':
            continue  # Only root-level clone/worktree metadata is outside the payload.
        need(not path.is_symlink(), 'symlink in payload: '+str(rel))
        need(path.is_file() or path.is_dir(), 'special file in payload: '+str(rel))
        if path.is_file():
            actual.add(str(rel))
    expected = {}
    for line in (ROOT/'checks.sha256').read_text().splitlines():
        need(bool(re.fullmatch(r'[0-9a-f]{64}  .+', line)), 'checksum record grammar')
        digest, name = line.split('  ', 1)
        need(safe_name(name) and name not in expected and name != 'checks.sha256'
             and PurePosixPath(name).parts[0] != '.git', 'checksum path')
        expected[name] = digest
    need(bool(expected), 'empty checksum manifest')
    generated = {'src/a348425'} if 'src/a348425' in actual else set()
    need(actual == set(expected) | {'checks.sha256'} | generated,
         'payload inventory mismatch; missing='+str(sorted(set(expected)-actual))
         +'; unexpected='+str(sorted(actual-set(expected)-{'checks.sha256'}-generated)))
    for name, digest in expected.items():
        need(sha((ROOT/name).read_bytes()) == digest, 'payload identity: '+name)
    return len(expected)+1, bool(generated)


def pairs(raw):
    return [tuple(map(int, line.split())) for line in raw.splitlines()
            if line and not line.startswith(b'#')]


def restore(path, target, rows):
    expected = {row['path']: row for row in rows}
    need(len(expected) == len(rows), 'duplicate archive index path')
    with tarfile.open(path) as archive:
        members = archive.getmembers()
        names = [m.name for m in members]
        need(len(names) == len(set(names)) and set(names) == set(expected),
             'exact archive member inventory: '+path.name)
        for member in members:
            need(member.isfile() and safe_name(member.name), 'unsafe archive member')
            raw = archive.extractfile(member).read()
            row = expected[member.name]
            need(len(raw) == row['bytes'] and sha(raw) == row['sha256'],
                 'archive member identity: '+member.name)
            out = target/member.name
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(raw)
            out.chmod(member.mode & 0o777)


def invoke(command, *, cwd=None, expected=0):
    env = dict(os.environ)
    for key in ('CPPFLAGS', 'LDFLAGS', 'LDLIBS', 'MAKEFLAGS', 'MFLAGS',
                'MAKEOVERRIDES', 'PYTHONPATH', 'PYTHONHOME', 'PYTHONOPTIMIZE'):
        env.pop(key, None)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    result = subprocess.run(command, cwd=cwd, env=env, text=True,
                            capture_output=True, timeout=90)
    need(result.returncode == expected,
         'command failed: '+repr(command)+': '+result.stderr)
    return dict(command=[str(v) for v in command], returncode=result.returncode,
                stdout=result.stdout, stderr=result.stderr)


def python(path, *args, siblings=False):
    flags = ['-E', '-s', '-B'] if siblings else ['-I', '-B']
    return invoke([sys.executable, *flags, str(path), *map(str, args)])


def load_module(path):
    spec = importlib.util.spec_from_file_location('historical_verifier', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    need(len(sys.argv) == 1, 'fixed retained-data audit accepts no arguments')
    count, has_build = inventory()  # Reject changed/missing/extra bytes before execution.
    import sympy
    need(sympy.__version__ == '1.12', 'recorded SymPy 1.12 required')
    braw = (ROOT/'data/b348425.txt').read_bytes()
    araw = (ROOT/'data/a348425.txt').read_bytes()
    for raw in (braw, araw):
        need(raw.endswith(b'\n\n') and not raw.endswith(b'\n\n\n')
             and b'\r' not in raw, 'canonical LF LF framing')
    canonical, documentary = pairs(braw), pairs(araw)
    need(len(canonical) == len(documentary) == 9114, 'canonical row count')
    need([i for i, n in canonical] == list(range(1, 9115)), 'index continuity')
    need([(row[0], row[2]) for row in documentary] == canonical, 'direct a/b correspondence')
    roots = [math.isqrt(n) for i, n in canonical]
    need(all(r*r == n for r, (i, n) in zip(roots, canonical)), 'square inputs')
    need(all(a < b for a, b in zip(roots, roots[1:])), 'ordered distinct roots')
    history = json.loads((ROOT/'proof/map.json').read_text())
    executions = []
    with tempfile.TemporaryDirectory(prefix='a348425-public-') as td:
        temp = Path(td)
        hist, extra = temp/'hist', temp/'extra'
        restore(ROOT/'proof/run.tgz', hist, history['members'])
        restore(ROOT/'proof/extra.tgz', extra, history['support_members'])
        old = (hist/'src/a348425_v2.c').read_text()
        public = (ROOT/'src/a348425.c').read_text()
        need(old.count('"a348425_v2.c"') == 1 and
             old.replace('"a348425_v2.c"', '"a348425.c"') == public,
             'exact pathname-only C transformation')
        need('a348425_v' not in public, 'versioned public source identity')
        oldmake = (hist/'src/Makefile').read_text()
        wanted = oldmake.replace('a348425_v2.c', 'a348425.c').replace(
            'check: a348425\n\tpython3 -B ../checks/verify.py\n\tpython3 -B ../checks/recover.py',
            'check:\n\tpython3 -I -B ../check/a348425_package.py')
        need(wanted == (ROOT/'src/Makefile').read_text(),
             'exact public source/check routing transformation')
        build = temp/'build'
        build.mkdir()
        for name in ('a348425.c', 'Makefile'):
            (build/name).write_bytes((ROOT/'src'/name).read_bytes())
        executions.append(invoke(['make', 'all'], cwd=build))
        public_binary = sha((build/'a348425').read_bytes())
        if has_build:
            need(sha((ROOT/'src/a348425').read_bytes()) == public_binary,
                 'existing generated binary differs from documented default build')
        rejected = invoke([str(build/'a348425'), 'verify', str(hist/'runs/c01')], expected=1)
        need('identity changed' in rejected['stderr'], 'foreign build rejection reason')
        executions.append(rejected)
        original = hist/'src/a348425'
        executions.append(invoke([str(original), 'verify', str(hist/'runs/c01')]))
        executions.append(python(hist/'checks/verify.py', '--run', hist/'runs/c01'))
        verifier = load_module(hist/'checks/verify.py')
        cfg, hits = verifier.records(hist/'runs/c01', original)
        prefix = pairs((hist/'data/b348425.txt').read_bytes())
        need(len(prefix) == 197 and len(hits) == 8917 and
             prefix+[(198+j, h[1]) for j, h in enumerate(hits)] == canonical,
             '197+8917 exact indexed regeneration')
        need(pairs((extra/'public.txt').read_bytes()) == canonical[:33], 'public common prefix')
        census = json.loads(gzip.decompress((extra/'census.gz').read_bytes()))
        need(census['oracle_sha256'] == sha((ROOT/'check/finite.py').read_bytes()),
             'original finite oracle identity')
        need(census['interval'] == [6501, 1000000] and census['inputs'] == 993500
             and len(census['hits']) == 162, 'finite receipt domain')
        need([(36+j, row[1]) for j, row in enumerate(census['hits'])] == prefix[35:],
             'finite receipt and baseline197')
        finite_cfg, finite_hits = verifier.records(extra/'tail', original)
        need([finite_cfg['start'], finite_cfg['end']] == [6501, 1000000]
             and [list(row) for row in finite_hits] == census['hits'],
             'finite producer chain and original census equality')
        windows = []
        for lo, hi in ((1000001, 1001419), (100000001, 100001000),
                       (1000000001, 1000001000), (9999999001, 10000000000)):
            found = [w for r in range(lo, hi+1) if (w := verifier.witness(r))]
            need(found == [h for h in hits if lo <= h[0] <= hi] == [],
                 'complete negative window')
            windows.append(dict(low=lo, high=hi, inputs=hi-lo+1, hits=0))
        executions.append(python(ROOT/'check/baseline.py', ROOT/'check/indep.c',
                                 ROOT/'data/b348425.txt'))
        executions.append(python(ROOT/'check/a348425_afile.py'))
        stats = []
        for name in ('b348425.txt', 'a348425.txt'):
            execution = python(ROOT/'paper/analysis.py', ROOT/'data'/name)
            stats.append(json.loads(execution['stdout']))
            executions.append(execution)
        need({k: v for k, v in stats[0].items() if k != 'input_sha256'} ==
             {k: v for k, v in stats[1].items() if k != 'input_sha256'},
             'both canonical-format finite analyses agree')
        trial = python(ROOT/'check/recheck.py', ROOT/'data/b348425.txt',
                       ROOT/'data/a348425.txt', ROOT/'paper/A348425_v3.tex', extra)
        checked = json.loads(trial['stdout'])
        need(checked['positives_rechecked'] == 9114 and checked['afile_equals_bfile']
             and checked['classes'] == checked['longtable_rows'] == 35
             and checked['class_members'] == checked['longtable_sum_h'] == 130
             and checked['longtable_matches'] and checked['longtable_sorted_by_m'],
             'independent trial arithmetic and manuscript certificate table')
        need(checked['paired']['agree'] and checked['paired']['squares'] == 72
             and checked['paired']['rows'] == [10000, 10000], 'paired provider composition')
        need(checked['prov_028871']['row8889'] == [8889, 10009802399]
             and [checked['prov_'+s]['mapped'] for s in ('028871','028873','201787')]
             == [8888, 45, 4] and all(checked['prov_'+s]['incl']
                 for s in ('028871','028873','201787')), 'provider identities and inclusions')
        need(checked['new_witness']['isprime'] and checked['new_witness']['is100049sq']
             and checked['new_witness']['p2'] == 100196144067026155201,
             'unindexed upper witness')
        executions.append(trial)
        executions.append(python(ROOT/'check/native.py', siblings=True))
    print(json.dumps(dict(author='Carlo Corti', status='PASS', payload_files=count,
        historical_archive_members=len(history['members']),
        supplemental_archive_members=len(history['support_members']),
        canonical_rows=9114, prefix_rows=197, campaign_hits=8917,
        negative_windows=windows, first_unresolved_index=9115,
        original_binary_sha256=history['binary_sha'],
        normalized_binary_sha256=public_binary,
        scope='Retained records, positive arithmetic and fixed bounded windows; no global rerun',
        finite_census='Original 993500-root execution receipt reconciled, not repeated',
        validation_classes=dict(sympy='Direct composition/state/finite analyses; shared backend',
            trial='Separate pure-Python factor-multiset positive checker; Claude provenance',
            c_windows='Separate Claude C multiset code, fixed intervals only',
            native='Shared producer helpers; not independent arithmetic',
            seals='Integrity and recorded completion, not independent negative enumeration'),
        executions=executions), indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, IndexError, TypeError,
            subprocess.TimeoutExpired, tarfile.TarError) as exc:
        raise SystemExit('FAIL: '+str(exc))
