/* Reviewer's independent enumerator for A348425 (not derived from a348425.c).
 * For each r in [lo,hi]: factor r and d=D(r) by trial division + Miller-Rabin
 * (bases = first 12 primes, deterministic for n < 3.18e23) + Brent rho;
 * build the prime multiset of x = 2*r*d = D(r^2) and evaluate D(x) directly
 * in unsigned __int128; accept iff D(x) is an exact square.
 * It deliberately does NOT use the identity D^2(r^2) = r d + 2 d^2 + 2 r D(d).
 * Output: one root per hit, ascending. Usage: indep LO HI
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <math.h>
typedef unsigned __int128 u128;
typedef uint64_t u64;

static u64 mulm(u64 a, u64 b, u64 m) { return (u64)((u128)a*b % m); }
static u64 powm(u64 a, u64 e, u64 m) { u64 r = 1; a %= m; while (e) { if (e & 1) r = mulm(r, a, m); a = mulm(a, a, m); e >>= 1; } return r; }
static int isprime(u64 n) {
    static const u64 P[12] = {2,3,5,7,11,13,17,19,23,29,31,37};
    if (n < 2) return 0;
    for (int i = 0; i < 12; i++) { if (n == P[i]) return 1; if (n % P[i] == 0) return 0; }
    u64 d = n - 1; int s = 0; while (!(d & 1)) { d >>= 1; s++; }
    for (int i = 0; i < 12; i++) {
        u64 x = powm(P[i], d, n);
        if (x == 1 || x == n - 1) continue;
        int ok = 0;
        for (int j = 1; j < s; j++) { x = mulm(x, x, n); if (x == n - 1) { ok = 1; break; } }
        if (!ok) return 0;
    }
    return 1;
}
static u64 gcd(u64 a, u64 b) { while (b) { u64 t = a % b; a = b; b = t; } return a; }
static u64 brent(u64 n) {
    if (!(n & 1)) return 2;
    for (u64 c = 1;; c++) {
        u64 y = 2, x, g = 1, q = 1, ys = 2, m = 128, r = 1;
        do {
            x = y;
            for (u64 i = 0; i < r; i++) y = (mulm(y, y, n) + c) % n;
            u64 k = 0;
            do {
                ys = y;
                for (u64 i = 0; i < m && i < r - k; i++) {
                    y = (mulm(y, y, n) + c) % n;
                    q = mulm(q, x > y ? x - y : y - x, n);
                }
                g = gcd(q, n); k += m;
            } while (k < r && g == 1);
            r <<= 1;
        } while (g == 1);
        if (g == n) {
            do { ys = (mulm(ys, ys, n) + c) % n; g = gcd(x > ys ? x - ys : ys - x, n); } while (g == 1);
        }
        if (g != n) return g;
    }
}
typedef struct { u64 p[64]; int e[64]; int k; } Fac;
static void add(Fac *f, u64 p, int e) {
    for (int i = 0; i < f->k; i++) if (f->p[i] == p) { f->e[i] += e; return; }
    if (f->k >= 64) { fprintf(stderr, "fac overflow\n"); exit(3); }
    f->p[f->k] = p; f->e[f->k] = e; f->k++;
}
static void rec(Fac *f, u64 n) {
    if (n == 1) return;
    if (isprime(n)) { add(f, n, 1); return; }
    u64 d = brent(n);
    if (d <= 1 || d >= n || n % d) { fprintf(stderr, "split failure %llu\n", (unsigned long long)n); exit(4); }
    rec(f, d); rec(f, n / d);
}
static void factor(Fac *f, u64 n) {
    for (u64 p = 2; p < 200 && p * p <= n; p += (p == 2 ? 1 : 2)) {
        int e = 0; while (n % p == 0) { n /= p; e++; } if (e) add(f, p, e);
    }
    rec(f, n);
}
static u128 Dfac(const Fac *f, u128 n) {           /* D(n) given its factorization */
    u128 s = 0; for (int i = 0; i < f->k; i++) s += (u128)f->e[i] * (n / f->p[i]); return s;
}
static int issq(u128 y, u64 *root) {
    long double z = sqrtl((long double)y); u128 q = (u128)z;
    while (q * q > y) q--;
    while ((q + 1) * (q + 1) <= y) q++;
    *root = (u64)q; return q * q == y;
}
int main(int argc, char **argv) {
    u64 lo = strtoull(argv[1], 0, 10), hi = strtoull(argv[2], 0, 10);
    const u64 CH = 1 << 20;
    for (u64 base = lo; base <= hi; base += CH) {
        u64 top = base + CH - 1 > hi ? hi : base + CH - 1;
        size_t w = top - base + 1;
        unsigned char *hit = calloc(w, 1);
        #pragma omp parallel for schedule(dynamic, 1024)
        for (size_t i = 0; i < w; i++) {
            u64 r = base + i, R;
            if (r < 2) { hit[i] = 1; continue; }            /* D^2(0)=D^2(1)=0, square */
            Fac fr = {0}; factor(&fr, r);
            u128 d128 = Dfac(&fr, r); u64 d = (u64)d128;
            if (d128 >> 64) { fprintf(stderr, "d width\n"); exit(5); }
            Fac fx = {0};                                   /* x = 2 r d */
            add(&fx, 2, 1);
            for (int j = 0; j < fr.k; j++) add(&fx, fr.p[j], fr.e[j]);
            Fac fd = {0}; factor(&fd, d);
            for (int j = 0; j < fd.k; j++) add(&fx, fd.p[j], fd.e[j]);
            u128 x = (u128)2 * r * d;
            u128 y = Dfac(&fx, x);
            if (issq(y, &R)) hit[i] = 1;
        }
        for (size_t i = 0; i < w; i++) if (hit[i]) printf("%llu\n", (unsigned long long)(base + i));
        free(hit);
    }
    return 0;
}
