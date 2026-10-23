# A348425: squares with square second arithmetic derivative

Author: Carlo Corti (Independent researcher), carlo.corti@outlook.com.

**PACKAGE_DRAFT — AWAITING AUTHOR INSPECTION.** Prepared October 23, 2026.
The intended initial version is `v1.0`; its citation date is a preparation date,
not evidence of publication. The intended repository is
https://github.com/carcorti/A348425 and the designated draft archive sentinel is
https://doi.org/10.5281/zenodo.xxxxxxxx. No public release is asserted here.

## Mathematical result and data

The arithmetic derivative has `D(0)=D(1)=0`, `D(p)=1` for primes and
`D(u*v)=u*D(v)+v*D(u)`. This project enumerates the nonnegative squares `n=r*r`
for which `D(D(n))` is square, including zero. With `d=D(r)` and `e=D(d)`,
the exact root identity is `D(D(r*r))=r*d+2*d*d+2*r*e`.

The canonical data contain **9,114 consecutive terms**, indexed from 1,
with completed input-root coverage through `r=10000000000`. The acquired public
snapshot contained 33 terms. The stages are 33 → 35 → 197 → 9114:

| Stage | Root interval/frontier | Added terms | Evidence |
|---|---|---:|---|
| Acquired public snapshot | through 5623 | 33 | Exact snapshot and original table retained |
| Initial replay | 5624..6500 | 2 | Complete interval; roots 5625 and 5927 |
| Finite continuation | 6501..1000000 | 162 | Completed finite producer and separate Python census |
| Official final campaign | 1000001..10000000000 | 8917 | Two completed sealed contiguous segments |

A separate complete check of `0..6500` on October 23 closes the originally
admitted public-prefix dependency. It adds no terms and is not retrodated to
the October 22 campaign. The last indexed term is
`a(9114)=99948010099131627889`, with root `9997400167`.
Index **9115 remains unresolved**; its established bound is
`100000000000000000000 < a(9115) <= 100196144067026155201`.
The upper witness has root `10009802399` and is **unindexed**.

`data/b348425.txt` contains exactly `i a(i)` with indices 1..9114.
`data/a348425.txt` is the documentary table with columns
`i r n D(n) D(D(n)) R`, where `n=r*r` and `D(D(n))=R*R`.
It documents these same contiguous terms, not sparse values after a missing
index. Both canonical files end with exactly two LF bytes: one empty last line.
The a-file is included because its six validated columns are independently useful.

The manuscript proves the reduced-core/rate square criterion and disjoint
infinite scale families. Its 35 observed positive-rate classes have 130 members;
four classes were present in earlier notes and 31 were derived from the finite
consolidated data. These counts are not a global classification or density law.
The current monolithic source is [paper/A348425_v3.tex](paper/A348425_v3.tex).

## Essential inventory

| Path | Purpose |
|---|---|
| `src/a348425.c`, `src/Makefile` | Stable normalized C17 producer and exact build recipe |
| `paper/A348425_v3.tex` | Current English manuscript, inline bibliography, no external assets |
| `paper/analysis.py` | Original finite analysis/certificates; accepts either canonical data format |
| `data/b348425.txt`, `data/a348425.txt` | Canonical indexed data and documentary witnesses |
| `proof/run.tgz`, `proof/map.json` | Actual historical source, Makefile, executable, verifier, baseline197 and seven final-run files; exact member identities |
| `proof/extra.tgz` | Thirty essential finite-run/receipt/provider/entry inputs; indexed in `proof/map.json` |
| `proof/name.diff` | Exact historical-to-public source/build transformation |
| `check/a348425_package.py` | Single fail-closed bounded reproduction driver |
| `check/baseline.py`, `check/indep.c` | Complete small baseline and fixed C windows, distinct multiset arithmetic |
| `check/finite.py` | Original separate finite-census implementation, matching the retained receipt |
| `check/recheck.py` | Original separate pure-trial positive/certificate/provider checker |
| `check/a348425_afile.py` | Direct documentary composition and indexed a/b correspondence |
| `check/native.py`, `check/verify.py` | Shared C helper fixtures and their separately computed expected coordinates |
| `check/recover.py`, `check/oper.py` | Retained development recovery/crash/I/O test methods; not run by the bounded driver |
| `CITATION.cff`, `LICENSE`, `NOTICE.md`, `deps.txt`, `checks.sha256` | Citation, existing project MIT license, upstream attribution, pinned Python dependency, exact payload inventory |

No private review prose, chat prompts, obsolete manuscripts, caches, auxiliary
TeX files, benchmark debris or duplicate public executable is included. Research
articles are cited in the manuscript rather than redistributed without a basis
for redistribution. The original consulted book was not read in full; no claim
of absolute bibliographic priority is made.

## Build and reproduce the retained checks

The tested environment is Linux Mint 22.3, x86-64 LP64, GCC 13.3.0, GNU OpenMP
(libgomp), OpenSSL 3.0.13/libcrypto, libm, Python 3.12.3 and **SymPy 1.12**.
A C17 compiler with unsigned 128-bit support, make, OpenSSL development headers
and OpenMP are needed. The preserved Linux executable additionally needs
compatible libcrypto.so.3 and libgomp.so.1. Dependencies are not vendored.
The Python version pin deliberately rejects untested SymPy versions.

For an isolated Python environment, from this directory:

```sh
python3 -m venv /tmp/a348425-env
/tmp/a348425-env/bin/python -m pip install -r deps.txt
/tmp/a348425-env/bin/python -I -B check/a348425_package.py > /tmp/a348425-check.json
```

If the tested dependencies are already available, the single command is:

```sh
python3 -I -B check/a348425_package.py > /tmp/a348425-check.json
```

The equivalent `make -C src check` routes to that same retained-data driver.
The public producer can separately be built with `make -C src` and its generated
binary removed with `make -C src clean`. The driver builds a disposable copy
itself. If a generated `src/a348425` already exists, it must match this default
build; a stale or differently configured binary is rejected. Write verification
outputs outside the payload so the exact inventory remains meaningful.

Expected top-level result: `status: PASS`, `canonical_rows: 9114`,
`prefix_rows: 197`, `campaign_hits: 8917`, `first_unresolved_index: 9115`.
The command returns nonzero on an unmet obligation, build error or timeout.
It performs no installation, network request, PDF build, `init` or `next`.
The fixed root checks and native scalar fixtures do not start a new campaign.

The bounded driver verifies:

1. Exact inventory and checksums before executable checks; unexpected, missing,
   changed, symlinked or special files fail. Only root `.git` metadata and the
   specifically checked generated program are accepted outside the manifest.
2. Original archive members, source/build identities, original executable
   `verify` and original Python verifier with `--run`; ordered segment seals,
   completed cursors and joins; baseline197 plus 8917 hits regenerates the
   complete canonical b-file. The distinct normalized build must reject the
   original run's bindings rather than masquerade as its producer.
3. The historical finite producer chain and the original 162-hit census receipt
   agree with baseline197 and with the original `check/finite.py` identity.
   The full 993500-root census is **not repeated** by this command.
4. Complete baseline `0..6500`: 35 hits by direct trial composition and the
   separately supplied C. Three fixed 129-root C windows at first/last campaign
   hits and the segment join give respectively 1/1/0 hits (listed order in the
   executable receipt is first/join/last: 1/0/1).
5. Four complete SymPy windows: `1000001..1001419`,
   `100000001..100001000`, `1000000001..1000001000`,
   `9999999001..10000000000`; 4419 inputs, all negative.
6. All documentary arithmetic and a/b indexing, both finite-analysis formats,
   all 35 certificates and their 130 observed members; separate pure-Python
   trial arithmetic reproduces the manuscript's table.
7. All 10000 paired A056798/A192084 derivatives (72 squares), complete retained
   provider mappings (8888/45/4), the A028871 witness at row 8889 and its trial
   primality; plus shared-producer C square, primality, width, partition and
   forced-fallback fixtures.

Every verbose subcommand receipt is retained in the returned JSON. Two SymPy
modes are shared-backend checks, not two independent backends. The trial Python
and multiset C methods differ arithmetically from the producer but have Claude
provenance, correlated with earlier Claude reviews. Native fixtures reuse the
producer and are not independent arithmetic. Seals and positive arithmetic do
not constitute independent enumeration of all final-campaign negatives.
No complete second enumeration of `(1000000,10000000000]` is claimed.

The preserved development scripts contain producer-driving regression modes;
they are supplied to document the checks used during development and are not
part of the default retained-data command. Running them is a separate optional
activity, never an instruction to resume or repeat the official campaign.

Original helper docstrings also retain historical invocation or output aliases,
such as `indep.py` in `check/finite.py`, `ZIPDIR` in `check/recheck.py`, and
`outputs/paper/stats.json` in `paper/analysis.py`. These comments are preserved
with the original checker identities. Use the current inventory paths and the
default command above; its driver restores the required inputs automatically.
To run the finite analysis alone from this directory, write its output outside
the payload:

```sh
python3 -I -B paper/analysis.py data/a348425.txt > /tmp/a348425-stats.json
```

For TeX source checking without creating a PDF:

```sh
mkdir -p /tmp/a348425-tex
pdflatex -interaction=nonstopmode -halt-on-error -draftmode -output-directory=/tmp/a348425-tex paper/A348425_v3.tex
pdflatex -interaction=nonstopmode -halt-on-error -draftmode -output-directory=/tmp/a348425-tex paper/A348425_v3.tex
```

No external TeX assets or BibTeX/Biber are needed. Visual inspection of a future
PDF is a separate task.

## Historical identity and compressed inputs

Carlo Corti executed the official campaign using `a348425_v2.c` and its original
Makefile/executable. Those exact bytes remain in `proof/run.tgz` (12 members).
The public `a348425.c` changes one neighboring-source filename literal. Its
Makefile preserves the compiler/linker flags and changes the source name and
check routing. The current check recipe reproduces retained data and bounded
fixtures; it does not launch the older recovery campaign fixtures. All changes
are shown in `proof/name.diff`. The normalized build did **not** produce the
historical results; the historical source name is not an alternate live producer.

`proof/extra.tgz` contains `tail/` (11 original finite-run files), `census.gz`
(the original independent execution receipt), `public.txt` (the acquired
33-term table), `more/` (five complete gzip provider tables), and `entry/`
(12 exact acquired OEIS entry texts, with contributor/date metadata).
`proof/map.json` records every restored path, hash and byte count. Its
`support_bytes` fields give compressed, tar and member-payload sizes.
Both archives restore only in temporary storage during the driver; never
restore historical sources/data over current workspace or publication files.
To inspect manually, extract into a new empty disposable directory using
`tar -xzf` on each archive. All names are short except meaningful TeX/C/Python
program names, whose established names are preserved.

The two campaign segments have 6792 and 2125 hits. Their saved internal counters
sum to about 48 minutes 46 seconds, excluding some I/O/startup/closure cost.
Campaign wall time, peak RSS and saved fallback frequency are unavailable.
The program's numeric root capacity `1E12` is not coverage through that bound.
The expected 9114-row data include a completed negative tail through `1E10`,
not merely through the last positive root.

## Attribution and citation

The existing [MIT license](LICENSE) is preserved for the project software and
associated documentation. Retained OEIS text/tables keep their upstream terms
and credits in [NOTICE.md](NOTICE.md); the project license does not relicense
those sources. The original helper sources retain their provenance comments.

Use [CITATION.cff](CITATION.cff) for the software and preferred manuscript
citation. Version/date and repository/archive locators are provisional until
publication. The exact Zenodo placeholder is intentional and must stay until
Carlo supplies the verified official locator. This local preparation is not a
PRE-UPLOAD PASS or a verification of remotely distributed artifacts.
