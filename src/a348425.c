/* A348425: squares r^2 whose composed arithmetic derivative D(D(r^2)) is square.
 * Copyright (c) 2026 Carlo Corti. Linux LP64; C17 + u128, OpenMP, libcrypto, libm.
 * d=D(r), e=D(d): y=r*d+2*d*d+2*r*e. D(0)=D(1)=0; no prime/family filter.
 * CAP is supported numeric capacity, not authority or completed coverage.
 * Five-column hit rows: r,n,D(n),D^2(n),R. No sequence indices assigned here.
 * State `next` is the first unprocessed root, including high+1 for completion.
 * A next invocation closes at most one segment. Complete internal blocks persist;
 * interrupted blocks repeat. No intra-factor checkpoint. No mathematical subprocess.
 * Generic durability/factor components adapted from Carlo Corti's A249107;
 * predicate, numeric envelope, schema and partition independently specialized.
 */
#define _POSIX_C_SOURCE 200809L
#include <ctype.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <limits.h>
#include <openssl/evp.h>
#include <signal.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/file.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>
#include <math.h>
#include <sys/statvfs.h>
#ifdef _OPENMP
#include <omp.h>
#endif

__extension__ typedef unsigned __int128 u128;
/* r<=CAP; d<=F(CAP), e<=F(F(CAP)); all products widened first. */
#define CAP UINT64_C(1000000000000)
#define MAX_D UINT64_C(19500000000000)
#define MAX_E UINT64_C(429000000000000)
#define MAX_X ((u128)UINT64_C(3900000000000000)*UINT64_C(10000000000))
#define MAX_Y ((u128)UINT64_C(1638000000000000000)*UINT64_C(1000000000))
#define MAX_ROOT UINT64_C(40472212689696)
#define MAX_SEGMENTS UINT64_C(512)
#ifndef A348425_SOURCE_SHA
#error "build using the identity-binding src/Makefile"
#endif
#ifndef A348425_MAKE_SHA
#error "build using the identity-binding src/Makefile"
#endif
#define MIN_BLOCK UINT64_C(16384)
#define MAX_BLOCK UINT64_C(65536)
#define MAX_THREADS 16
#define MAX_PATH 4096
#define HASH_LEN 64

_Static_assert(SIZE_MAX == UINT64_MAX && sizeof(off_t) >= 8, "LP64 size/file domain required");
_Static_assert(ATOMIC_INT_LOCK_FREE == 2, "signal stop flag must be lock-free");
static _Atomic int stopped = 0;
static void on_signal(int signum) {
    (void)signum;
    atomic_store_explicit(&stopped, 1, memory_order_relaxed);
}
static bool stop_requested(void) {
    return atomic_load_explicit(&stopped, memory_order_relaxed) != 0;
}

static _Noreturn void die(const char *msg) {
    fprintf(stderr, "ERROR: %s\n", msg);
    exit(1);
}
static _Noreturn void sysdie(const char *msg) {
    int saved = errno;
    if (saved == EINTR && stop_requested()) exit(2);
    fprintf(stderr, "ERROR: %s: %s\n", msg, strerror(saved));
    exit(1);
}
static bool dec64(const char *s, uint64_t *out) {
    if (!s || !*s) return false;
    uint64_t v = 0;
    for (; *s; ++s) {
        if (*s < '0' || *s > '9') return false;
        unsigned d = (unsigned)(*s - '0');
        if (v > (UINT64_MAX - d) / 10) return false;
        v = v * 10 + d;
    }
    *out = v;
    return true;
}
static bool dec128(const char *s, u128 *out) {
    if (!s || !*s) return false;
    u128 v = 0, top = ~(u128)0;
    for (; *s; ++s) {
        if (*s < '0' || *s > '9') return false;
        unsigned d = (unsigned)(*s - '0');
        if (v > (top - d) / 10) return false;
        v = v * 10 + d;
    }
    *out = v;
    return true;
}
static void fmt128(u128 v, char out[40]) {
    char tmp[40];
    size_t k = 0;
    do { tmp[k++] = (char)('0' + v % 10); v /= 10; } while (v);
    for (size_t j = 0; j < k; ++j) out[j] = tmp[k - 1 - j];
    out[k] = 0;
}
static uint64_t isqrt64(uint64_t x) {
    uint64_t lo = 0, hi = UINT64_C(4294967295);
    while (lo < hi) {
        uint64_t mid = lo + (hi - lo + 1) / 2;
        if (mid <= x / mid) lo = mid; else hi = mid - 1;
    }
    return lo;
}
static uint64_t ns_now(void) {
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t)) sysdie("clock_gettime");
    if(t.tv_sec<0 || t.tv_nsec<0 || t.tv_nsec>=1000000000L)
        die("monotonic clock domain");
    u128 value=(u128)(uint64_t)t.tv_sec*UINT64_C(1000000000)+(uint64_t)t.tv_nsec;
    if(value>UINT64_MAX) die("monotonic clock width");
    return (uint64_t)value;
}
/* Main sets this immutable context before the OpenMP fork and changes it
   only after the implicit join. The deadline is the sole shared mutable field. */
static bool live_enabled=false;
static uint64_t live_target,live_segment,live_cursor,live_begin;
static _Atomic uint64_t next_note=0;
static _Thread_local uint64_t active_input=0;
static void heartbeat(uint64_t operand) {
    if(!live_enabled) return;
    uint64_t now=ns_now();
    uint64_t due=atomic_load_explicit(&next_note,memory_order_relaxed);
    if(now<due) return;
    if(now>UINT64_MAX-UINT64_C(30000000000)) die("heartbeat clock overflow");
    if(!atomic_compare_exchange_strong_explicit(&next_note,&due,
           now+UINT64_C(30000000000),memory_order_relaxed,memory_order_relaxed)) return;
    if(now<live_begin) die("monotonic clock wrapped");
    fprintf(stderr,"HEARTBEAT A348425 target=%" PRIu64 " segment=%" PRIu64
            " committed_next=%" PRIu64 " active_input=%" PRIu64
            " factor_operand=%" PRIu64 " call_elapsed_s=%.0f uncommitted_block\n",
            live_target,live_segment,live_cursor,active_input,operand,
            (double)(now-live_begin)/1e9);
}
static void path2(char out[MAX_PATH], const char *dir, const char *base) {
    int n = snprintf(out, MAX_PATH, "%s/%s", dir, base);
    if (n < 0 || n >= MAX_PATH) die("path too long");
}
static void sync_dir(const char *dir) {
    int fd = open(dir, O_RDONLY | O_DIRECTORY);
    if (fd < 0) sysdie("open directory");
    if (fsync(fd)) sysdie("fsync directory");
    if (close(fd)) sysdie("close directory");
}
static void hash_file(const char *path, char hex[HASH_LEN + 1]) {
    unsigned char digest[EVP_MAX_MD_SIZE], buf[16384];
    unsigned int length = 0;
    FILE *f = fopen(path, "rb");
    if (!f) sysdie("open hash input");
    EVP_MD_CTX *ctx = EVP_MD_CTX_new();
    if (!ctx) die("EVP allocation");
    if (EVP_DigestInit_ex(ctx, EVP_sha256(), NULL) != 1) die("EVP init");
    for (;;) {
        size_t n = fread(buf, 1, sizeof buf, f);
        if (n && EVP_DigestUpdate(ctx, buf, n) != 1) die("EVP update");
        if (n < sizeof buf) {
            if (ferror(f)) sysdie("read hash input");
            break;
        }
    }
    if (EVP_DigestFinal_ex(ctx, digest, &length) != 1 || length != 32)
        die("EVP final");
    EVP_MD_CTX_free(ctx);
    if (fclose(f)) sysdie("close hash input");
    static const char hexd[] = "0123456789abcdef";
    for (unsigned i = 0; i < 32; ++i) {
        hex[2*i] = hexd[digest[i] >> 4];
        hex[2*i+1] = hexd[digest[i] & 15];
    }
    hex[64] = 0;
}
/* Hash an exact serialized prefix, excluding the segment's own footer. */
static void hash_stream_prefix(FILE *f, off_t length,
                               char hex[HASH_LEN + 1]) {
    if (length < 0) die("negative hash prefix");
    unsigned char digest[EVP_MAX_MD_SIZE], buf[16384];
    unsigned int digest_length = 0;
    if (fseeko(f,0,SEEK_SET)) sysdie("seek hash prefix");
    EVP_MD_CTX *ctx = EVP_MD_CTX_new();
    if (!ctx) die("EVP allocation");
    if (EVP_DigestInit_ex(ctx, EVP_sha256(), NULL) != 1) die("EVP init");
    uint64_t remaining = (uint64_t)length;
    while (remaining) {
        size_t want = remaining < sizeof buf ? (size_t)remaining : sizeof buf;
        size_t n = fread(buf, 1, want, f);
        if (n != want) {
            if (ferror(f)) sysdie("read hash prefix");
            die("short hash prefix");
        }
        if (EVP_DigestUpdate(ctx, buf, n) != 1) die("EVP update");
        remaining -= n;
    }
    if (EVP_DigestFinal_ex(ctx, digest, &digest_length) != 1 ||
        digest_length != 32) die("EVP final");
    EVP_MD_CTX_free(ctx);
    static const char hexd[] = "0123456789abcdef";
    for (unsigned i = 0; i < 32; ++i) {
        hex[2*i] = hexd[digest[i] >> 4];
        hex[2*i+1] = hexd[digest[i] & 15];
    }
    hex[64] = 0;
}
static void hash_file_prefix(const char *path, off_t length,
                             char hex[HASH_LEN + 1]) {
    FILE *f = fopen(path,"rb");
    if (!f) sysdie("open hash prefix");
    hash_stream_prefix(f,length,hex);
    if (fclose(f)) sysdie("close hash prefix");
}
static bool valid_hash(const char *s) {
    if (strlen(s) != HASH_LEN) return false;
    for (size_t i = 0; i < HASH_LEN; ++i)
        if (!((s[i] >= '0' && s[i] <= '9') ||
              (s[i] >= 'a' && s[i] <= 'f'))) return false;
    return true;
}

typedef struct {
    uint64_t start, end, block, group, threads;
    char src_hash[65], make_hash[65], bin_hash[65], cfg_hash[65];
} Config;
typedef struct { uint64_t r, root; u128 n, x, y; } Hit;
typedef struct {
    uint64_t id, low, high, frontier, elapsed_ns;
    Hit *hits;
    size_t nhit, cap;
} Segment;
_Static_assert(sizeof(Hit) <= 80, "hit allocation budget");
static void free_seg(Segment *s) { free(s->hits); memset(s, 0, sizeof *s); }
static void push_hit(Segment *s, Hit h) {
    if (s->nhit == s->cap) {
        size_t next = s->cap ? s->cap * 2 : 8;
        if (next < s->cap || next > SIZE_MAX / sizeof(Hit)) die("hit capacity");
        Hit *p = realloc(s->hits, next * sizeof(Hit));
        if (!p) die("hit allocation");
        s->hits = p;
        s->cap = next;
    }
    s->hits[s->nhit++] = h;
}
static void state_name(char name[32], uint64_t id, bool sha) {
    if (id >= UINT64_C(65536)) die("segment ID exceeds format");
    snprintf(name, 32, "s%04" PRIx64 ".%s", id, sha ? "sha256" : "tsv");
}
static void space_guard(const char *dir,uint64_t needed) {
    struct statvfs v;if(statvfs(dir,&v))sysdie("statvfs");
    if((u128)v.f_bavail*v.f_frsize<(u128)needed+UINT64_C(67108864))
        die("insufficient free space: retain state and stop");
}
static void atomic_begin(FILE **fp, char tmp[MAX_PATH], const char *dir,
                         const char *base) {
    char dst[MAX_PATH];
    path2(dst, dir, base);
    int n = snprintf(tmp, MAX_PATH, "%s.tmp.%ld", dst, (long)getpid());
    if (n < 0 || n >= MAX_PATH) die("temporary path too long");
    int fd = open(tmp, O_CREAT | O_EXCL | O_WRONLY, 0600);
    if (fd < 0) sysdie("create temporary file");
    *fp = fdopen(fd, "w");
    if (!*fp) sysdie("fdopen");
}
static void atomic_end(FILE *fp, const char *tmp, const char *dir,
                       const char *base) {
    if (fflush(fp)) sysdie("flush temporary file");
    if (fsync(fileno(fp))) sysdie("fsync temporary file");
    if (fclose(fp)) sysdie("close temporary file");
    char dst[MAX_PATH];
    path2(dst, dir, base);
    if (rename(tmp, dst)) sysdie("rename temporary file");
    sync_dir(dir);
}
static bool exists(const char *path) {
    struct stat st;
    if (stat(path, &st) == 0) return true;
    if (errno == ENOENT) return false;
    sysdie("stat");
    return false;
}
static void write_cfg(const char *dir, const Config *c) {
    FILE *fp; char tmp[MAX_PATH];
    atomic_begin(&fp, tmp, dir, "run.cfg");
    if (fprintf(fp, "A348425-CFG-1\nstart\t%" PRIu64 "\nend\t%" PRIu64
                "\nblock\t%" PRIu64 "\ngroup\t%" PRIu64
                "\nthreads\t%" PRIu64 "\nsource_sha\t%s\nmakefile_sha\t%s"
                "\nbinary_sha\t%s\n",
                c->start,c->end,c->block,c->group,c->threads,
                c->src_hash,c->make_hash,c->bin_hash) < 0) sysdie("write config");
    atomic_end(fp,tmp,dir,"run.cfg");
}
/* Fixed grammar: every valid record, including the widest hit, is <256 bytes.
   Reject embedded NUL/CR and oversized/truncated records before allocation grows. */
static bool read_line(FILE *f, char **buf, size_t *cap) {
    if (*cap < 256) {
        char *p=realloc(*buf,256);
        if(!p) die("record allocation");
        *buf=p; *cap=256;
    }
    size_t n=0;
    for(;;) {
        int ch=fgetc(f);
        if(ch==EOF) {
            if(ferror(f)) sysdie("read record");
            if(n) die("truncated record");
            return false;
        }
        if(ch==0 || ch=='\r') die("NUL/CR in record");
        if(ch=='\n') { (*buf)[n]=0; return true; }
        if(n==255) die("oversized record");
        (*buf)[n++]=(char)ch;
    }
}
static void expect_eof(FILE *f, const char *what) {
    int ch=fgetc(f);
    if(ferror(f)) sysdie("read trailing record");
    if(ch!=EOF) die(what);
}
static void expect_key(FILE *f, char **line, size_t *cap, const char *key,
                       char **value) {
    if (!read_line(f,line,cap)) die("missing record field");
    size_t k = strlen(key);
    if (strncmp(*line,key,k) || (*line)[k] != '\t')
        die("record field mismatch");
    *value = *line+k+1;
}
static uint64_t field64(FILE *f, char **line, size_t *cap, const char *key) {
    char *v; uint64_t x;
    expect_key(f,line,cap,key,&v);
    if (!dec64(v,&x)) die("invalid integer field");
    return x;
}
static void fieldhash(FILE *f, char **line, size_t *cap, const char *key,
                      char hash[65]) {
    char *v;
    expect_key(f,line,cap,key,&v);
    if (!valid_hash(v)) die("invalid hash field");
    memcpy(hash,v,65);
}
static void config_load(const char *dir, Config *c) {
    char path[MAX_PATH];
    path2(path,dir,"run.cfg");
    FILE *f=fopen(path,"r");
    if (!f) sysdie("open run.cfg");
    char *line=NULL,*v=NULL; size_t cap=0;
    if (!read_line(f,&line,&cap) || strcmp(line,"A348425-CFG-1"))
        die("config magic");
    c->start=field64(f,&line,&cap,"start");
    c->end=field64(f,&line,&cap,"end");
    c->block=field64(f,&line,&cap,"block");
    c->group=field64(f,&line,&cap,"group");
    c->threads=field64(f,&line,&cap,"threads");
    fieldhash(f,&line,&cap,"source_sha",c->src_hash);
    fieldhash(f,&line,&cap,"makefile_sha",c->make_hash);
    fieldhash(f,&line,&cap,"binary_sha",c->bin_hash);
    (void)v;
    if (read_line(f,&line,&cap)) die("extra config record");
    if (ferror(f)) sysdie("read config");
    free(line);
    if (fclose(f)) sysdie("close config");
    if (c->end<c->start || c->end>CAP ||
        c->block<MIN_BLOCK || c->block>MAX_BLOCK ||
        (c->block & (c->block-1)) || !c->group ||
        c->group>MAX_SEGMENTS || c->group>(c->end-c->start)/c->block+1 ||
        !c->threads || c->threads>MAX_THREADS) die("invalid config domain");
    hash_file(path,c->cfg_hash);
}
static void own_identity(char src[65], char make[65], char bin[65]) {
    char exe[MAX_PATH], path[MAX_PATH];
    ssize_t n=readlink("/proc/self/exe",exe,sizeof exe-1);
    if (n<1 || n>=(ssize_t)sizeof exe-1) sysdie("read executable path");
    exe[n]=0;
    char *slash=strrchr(exe,'/');
    if (!slash) die("executable directory");
    hash_file(exe,bin);
    *slash=0;
    path2(path,exe,"a348425.c"); hash_file(path,src);
    path2(path,exe,"Makefile"); hash_file(path,make);
    if (strcmp(src,A348425_SOURCE_SHA) || strcmp(make,A348425_MAKE_SHA))
        die("binary is not bound to neighboring source and Makefile");
}
static void check_identity(const Config *c) {
    char a[65],b[65],d[65];
    own_identity(a,b,d);
    if (strcmp(a,c->src_hash)||strcmp(b,c->make_hash)||
        strcmp(d,c->bin_hash)) die("source, Makefile or binary identity changed");
}
static uint64_t num_segments(const Config *c) {
    uint64_t blocks=(c->end-c->start)/c->block+1;
    if(!c->group||c->group>MAX_SEGMENTS||c->group>blocks)
        die("segment count exceeds block/artifact budget");
    return c->group;
}
/* Each segment gets one block, plus a mildly front-loaded share of the rest.
   w(j)=j*(6S+1-j), denominator S*(5S+1); w(0)=0,w(S)=den.
   Strictly positive increments and one reserved block prove nonempty joins. */
static void seg_bounds(const Config *c,uint64_t id,uint64_t *low,uint64_t *high) {
    uint64_t count=num_segments(c);
    if(id>=count) die("segment ID outside range");
    u128 blocks=((u128)c->end-c->start+c->block)/c->block;
    u128 extra=blocks-count,den=(u128)count*(5*count+1);
    u128 begin=id+extra*id*(6*count+1-id)/den;
    u128 finish=id+1+extra*(id+1)*(6*count-id)/den;
    u128 l=(u128)c->start+begin*c->block;
    u128 h=(u128)c->start+finish*c->block-1;
    if(h>c->end)h=c->end;
    if(l>h||h>CAP)die("segment bounds");
    *low=(uint64_t)l;*high=(uint64_t)h;
}
static void hit_text(const Hit *h,char out[256]) {
    char n[40],x[40],y[40];fmt128(h->n,n);fmt128(h->x,x);fmt128(h->y,y);
    int z=snprintf(out,256,"%"PRIu64"\t%s\t%s\t%s\t%"PRIu64"\n",
                   h->r,n,x,y,h->root);
    if(z<0||z>=256)die("hit text overflow");
}
static void write_hit(FILE *fp,const Hit *h) {
    char row[256];hit_text(h,row);
    if(fputs(row,fp)==EOF)sysdie("write hit");
}
static void write_seg(const char *dir,const Config *c,const Segment *s) {
    char name[32],tmp[MAX_PATH]; FILE *fp;
    state_name(name,s->id,false);
    if(s->nhit>UINT64_MAX/192)die("state byte bound");
    space_guard(dir,(uint64_t)s->nhit*192+4096);
    atomic_begin(&fp,tmp,dir,name);
    if (fprintf(fp,"A348425-SEG-1\ncfg_sha\t%s\nid\t%04" PRIx64
                "\nlow\t%" PRIu64 "\nhigh\t%" PRIu64
                "\nnext\t%" PRIu64 "\nelapsed_ns\t%" PRIu64
                "\nhits\t%zu\n",c->cfg_hash,s->id,s->low,s->high,s->frontier,
                s->elapsed_ns,s->nhit)<0) sysdie("write segment");
    for (size_t i=0;i<s->nhit;++i) write_hit(fp,&s->hits[i]);
    if (fflush(fp)) sysdie("flush segment prefix");
    off_t prefix_length = ftello(fp);
    if (prefix_length < 0) sysdie("segment prefix offset");
    char digest[65];
    hash_file_prefix(tmp,prefix_length,digest);
    if (fprintf(fp,"state_sha\t%s\n",digest)<0) sysdie("write segment digest");
    atomic_end(fp,tmp,dir,name);
}
static bool read_seg(const char *dir,const Config *c,uint64_t id,Segment *s) {
    char name[32],path[MAX_PATH],*line=NULL; size_t linecap=0;
    state_name(name,id,false); path2(path,dir,name);
    FILE *f=fopen(path,"r");
    if (!f) { if (errno==ENOENT) return false; sysdie("open segment"); }
    memset(s,0,sizeof *s);
    if (fseeko(f,0,SEEK_END)) sysdie("seek segment end");
    off_t file_length = ftello(f);
    if (file_length < 0) sysdie("segment length");
    if (file_length < 75) die("missing or truncated segment digest");
    off_t prefix_length = file_length - 75;
    if (fseeko(f,prefix_length,SEEK_SET)) sysdie("seek segment digest");
    char footer[75], recorded[65], computed[65];
    if (fread(footer,1,sizeof footer,f) != sizeof footer) {
        if(ferror(f)) sysdie("read segment digest");
        die("missing or truncated segment digest");
    }
    if (memcmp(footer,"state_sha\t",10) || footer[74]!='\n')
        die("segment digest footer shape");
    memcpy(recorded,footer+10,64);
    recorded[64]=0;
    if (!valid_hash(recorded)) die("invalid segment digest");
    expect_eof(f,"extra or corrupt segment record");
    hash_stream_prefix(f,prefix_length,computed);
    if (strcmp(recorded,computed)) die("segment state digest mismatch");
    if (fseeko(f,0,SEEK_SET)) sysdie("seek segment fields");
    if (!read_line(f,&line,&linecap)||strcmp(line,"A348425-SEG-1"))
        die("segment magic");
    char cfg_hash[65];
    fieldhash(f,&line,&linecap,"cfg_sha",cfg_hash);
    if(strcmp(cfg_hash,c->cfg_hash)) die("segment config identity mismatch");
    if (!read_line(f,&line,&linecap)||strncmp(line,"id\t",3)||
        strlen(line+3)!=4) die("segment ID field");
    uint64_t parsed=0;
    for(int j=3;j<7;++j) {
        char ch=line[j];
        unsigned digit;
        if(ch>='0'&&ch<='9') digit=(unsigned)(ch-'0');
        else if(ch>='a'&&ch<='f') digit=(unsigned)(ch-'a'+10);
        else die("segment ID digit");
        parsed=parsed*16+digit;
    }
    if(parsed!=id) die("segment ID mismatch");
    s->id=id;
    s->low=field64(f,&line,&linecap,"low");
    s->high=field64(f,&line,&linecap,"high");
    s->frontier=field64(f,&line,&linecap,"next");
    s->elapsed_ns=field64(f,&line,&linecap,"elapsed_ns");
    uint64_t count=field64(f,&line,&linecap,"hits");
    uint64_t low,high; seg_bounds(c,id,&low,&high);
    if(s->low!=low||s->high!=high||s->frontier<low||
       s->frontier>high+1||count>s->frontier-low)
        die("segment bounds or hit count");
    uint64_t completed=s->frontier-low;
    if (s->frontier!=high+1 && completed%c->block)
        die("frontier not at block boundary");
    for (uint64_t i=0;i<count;++i) {
        if (!read_line(f,&line,&linecap)) die("missing hit row");
        char *parts[5]; parts[0]=line;
        for(int j=1;j<5;++j) {
            char *tab=strchr(parts[j-1],'\t');
            if(!tab||tab==parts[j-1])die("hit row shape");
            *tab=0;parts[j]=tab+1;
        }
        if(!*parts[4]||strchr(parts[4],'\t'))die("hit row shape");
        Hit h;
        if(!dec64(parts[0],&h.r)||!dec128(parts[1],&h.n)||
           !dec128(parts[2],&h.x)||!dec128(parts[3],&h.y)||
           !dec64(parts[4],&h.root))die("hit row integer");
        if(h.r>CAP||h.n!=(u128)h.r*h.r||h.x>MAX_X||h.y>MAX_Y||
           h.root>MAX_ROOT||(u128)h.root*h.root!=h.y)die("hit coordinate domain");
        if(h.r<low||h.r>=s->frontier||(s->nhit&&h.r<=s->hits[s->nhit-1].r))
            die("hit row order/range");
        push_hit(s,h);
    }
    off_t parsed_length = ftello(f);
    if (parsed_length < 0) sysdie("segment parsed offset");
    if (parsed_length != prefix_length) die("segment field/footer boundary");
    free(line); if(fclose(f)) sysdie("close segment");
    return true;
}

static uint64_t gcd64(uint64_t a,uint64_t b) {
    while(b) { uint64_t t=a%b; a=b; b=t; }
    return a;
}
static uint64_t mulmod(uint64_t a,uint64_t b,uint64_t m) {
    return (uint64_t)(((u128)a*b)%m);
}
static uint64_t powmod(uint64_t a,uint64_t e,uint64_t m) {
    uint64_t r=1;
    while(e) {
        if(e&1) r=mulmod(r,a,m);
        e>>=1;
        if(e) a=mulmod(a,a,m);
    }
    return r;
}
/* Deterministic for every uint64_t, not merely for a decimal subrange. */
static bool prime64(uint64_t n) {
    static const uint64_t small[]={2,3,5,7,11,13,17,19,23,29,31,37};
    if(n<2) return false;
    for(size_t i=0;i<sizeof small/sizeof small[0];++i) {
        if(n==small[i]) return true;
        if(n%small[i]==0) return false;
    }
    uint64_t d=n-1; unsigned s=0;
    while(!(d&1)) { d>>=1; ++s; }
    static const uint64_t bases[]={
        2,325,9375,28178,450775,9780504,1795265022
    };
    for(size_t i=0;i<sizeof bases/sizeof bases[0];++i) {
        uint64_t a=bases[i]%n;
        if(!a) continue;
        uint64_t x=powmod(a,d,n);
        if(x==1||x==n-1) continue;
        bool pass=false;
        for(unsigned j=1;j<s;++j) {
            x=mulmod(x,x,n);
            if(x==n-1) { pass=true; break; }
        }
        if(!pass) return false;
    }
    return true;
}
static uint64_t rho_step(uint64_t x,uint64_t c,uint64_t n) {
    return (uint64_t)(((u128)x*x+c)%n);
}
static uint64_t split64(uint64_t n,bool *fallback) {
    static const uint32_t small[]={2,3,5,7,11,13,17,19,23,29,31,37,
        41,43,47,53,59,61,67,71,73,79,83,89,97};
    for(size_t i=0;i<sizeof small/sizeof small[0];++i)
        if(n%small[i]==0) return small[i];
    /* Fixed seeds and effort make the fast path reproducible. */
#ifndef A348425_FORCE_FALLBACK
    for(uint64_t c=1;c<=32;++c) {
        uint64_t x=2+c,y=x,d=1;
        for(uint64_t k=0;k<100000 && d==1;++k) {
            if(stop_requested()) return 0;
            if((k & 4095)==0) heartbeat(n);
            x=rho_step(x,c,n);
            y=rho_step(rho_step(y,c,n),c,n);
            uint64_t delta=x>y?x-y:y-x;
            d=gcd64(delta,n);
        }
        if(d>1&&d<n) return d;
    }
#endif
    /* Exact terminating fallback. It can be slow on an adversarial
       semiprime; interruption is an incomplete block, never a miss. */
    *fallback=true;
    for(uint64_t p=101;p<=n/p;p+=2) {
        if(stop_requested()) return 0;
        if((p & UINT64_C(131071))==101) heartbeat(n);
        if(n%p==0) return p;
    }
    return 0;
}
static bool factor_rec(uint64_t n,uint64_t fac[64],unsigned *nf,
                       bool *fallback) {
    if(n==1) return true;
    if(prime64(n)) {
        if(*nf>=64) return false;
        fac[(*nf)++]=n;
        return true;
    }
    uint64_t d=split64(n,fallback);
    if(d<=1||d>=n||n%d) return false;
    return factor_rec(d,fac,nf,fallback) &&
           factor_rec(n/d,fac,nf,fallback);
}
static int cmp64(const void *a,const void *b) {
    uint64_t x=*(const uint64_t*)a,y=*(const uint64_t*)b;
    return (x>y)-(x<y);
}
static bool derivative64(uint64_t n,u128 *out,bool *fallback) {
    if(n<2) { *out=0; return true; }
    uint64_t fac[64]; unsigned nf=0;
    if(!factor_rec(n,fac,&nf,fallback)) return false;
    qsort(fac,nf,sizeof fac[0],cmp64);
    u128 prod=1,sum=0;
    for(unsigned i=0;i<nf;) {
        uint64_t p=fac[i]; unsigned e=0;
        if(!prime64(p)) return false;
        while(i<nf&&fac[i]==p) {
            prod*=p;
            if(prod>n) return false;
            ++e; ++i;
        }
        sum+=(u128)e*(n/p);
    }
    if(prod!=n) return false;
    *out=sum;
    return true;
}
/* Floating seed only: the acceptance decision is exact integer arithmetic. */
static uint64_t square_root(u128 y) {
    if(y>MAX_Y)die("square domain");
    uint64_t q=(uint64_t)sqrtl((long double)y);
    while((u128)q*q>y)--q;
    while((u128)(q+1)*(q+1)<=y)++q;
    return q;
}
/* -1 incomplete/error, 0 miss, 1 exact hit. No prime-root filter. */
static int predicate(uint64_t r,uint64_t d,Hit *hit,bool *fallback) {
    active_input=r;
    if(r>CAP||d>MAX_D||(r<2&&d))return -1;
    u128 e;
    if(stop_requested()||!derivative64(d,&e,fallback)||e>MAX_E)return -1;
    u128 x=2*(u128)r*d;
    u128 y=(u128)r*d+2*(u128)d*d+2*(u128)r*e;
    if(x>MAX_X||y>MAX_Y)return -1;
    unsigned mod=(unsigned)(y&15);
    if(mod!=0&&mod!=1&&mod!=4&&mod!=9)return 0;
    uint64_t q=square_root(y);
    if((u128)q*q!=y)return 0;
    if(hit)*hit=(Hit){.r=r,.n=(u128)r*r,.x=x,.y=y,.root=q};
    return 1;
}
static bool verified_hit(const Hit *h) {
    if(h->r>CAP)return false;
    bool fallback=false;u128 d;Hit fresh;
    if(!derivative64(h->r,&d,&fallback)||d>MAX_D)return false;
    if(predicate(h->r,(uint64_t)d,&fresh,&fallback)!=1)return false;
    return fresh.r==h->r&&fresh.n==h->n&&fresh.x==h->x&&fresh.y==h->y&&fresh.root==h->root;
}
typedef struct { uint32_t *v; size_t n; } Primes;
static Primes make_primes(uint64_t end) {
    uint64_t root=isqrt64(end);
    if(root>UINT32_MAX || root>SIZE_MAX-1) die("prime table width");
    size_t len=(size_t)root+1;
    uint8_t *mark=calloc(len,1);
    if(!mark) die("prime sieve allocation");
    for(uint64_t p=2;p<=root/p;++p)
        if(!mark[p])
            for(uint64_t q=p*p;q<=root;q+=p) mark[q]=1;
    Primes a={0};
    if(len>SIZE_MAX/sizeof(uint32_t)) die("prime capacity");
    a.v=malloc(len*sizeof(uint32_t));
    if(!a.v) die("prime list allocation");
    for(uint64_t p=2;p<=root;++p) if(!mark[p]) a.v[a.n++]=(uint32_t)p;
    free(mark);
    return a;
}
static bool block_scan(const Config *c,const Primes *pr,Segment *s,
                       uint64_t low,uint64_t high,uint64_t *fallbacks) {
    size_t saved_hits=s->nhit;
    size_t width=(size_t)(high-low+1);
    if(high<low || width>MAX_BLOCK) die("block domain");
    uint64_t *residual=malloc(width*sizeof(uint64_t));
    uint64_t *d1=calloc(width,sizeof(uint64_t));
    uint8_t *flags=malloc(width);
    if(!residual||!d1||!flags) die("block allocation");
    for(size_t i=0;i<width;++i) residual[i]=low+i;
    for(size_t j=0;j<pr->n;++j) {
        uint64_t p=pr->v[j];
        if(p>high/p) break;
        u128 first=((u128)low+p-1)/p*p;
        for(uint64_t v=(uint64_t)first;v<=high;) {
            size_t i=(size_t)(v-low);
            unsigned e=0;
            while(residual[i]>1&&residual[i]%p==0) { residual[i]/=p; ++e; }
            if(e) {
                u128 add=(u128)e*(v/p);
                if(add>UINT64_MAX-d1[i]) die("sieve derivative overflow");
                d1[i]+=(uint64_t)add;
            }
            if(high-v<p) break;
            v+=p;
        }
    }
    for(size_t i=0;i<width;++i) {
        if(residual[i]>1) {
            u128 add=(u128)(low+i)/residual[i];
            if(add>UINT64_MAX-d1[i]) die("residual derivative overflow");
            d1[i]+=(uint64_t)add;
        }
        /* The residual is 1 or prime: every composite <= high had a
           factor <= sqrt(high), and every such prime was sieved. */
    }
    uint64_t fb=0;
#ifdef _OPENMP
#pragma omp parallel for schedule(dynamic,64) num_threads((int)c->threads) reduction(+:fb)
#endif
    for(size_t i=0;i<width;++i) {
        active_input=low+i;
        if((i & 4095)==0) heartbeat(0);
        if(stop_requested()) { flags[i]=2; continue; }
        bool fallback=false;
        Hit h;
        int result=predicate(low+i,d1[i],&h,&fallback);
        if(fallback) ++fb;
        flags[i]=(stop_requested()||result<0)?2:(result?1:0);
    }
    *fallbacks+=fb;
    bool complete=true;
    for(size_t i=0;i<width;++i) if(flags[i]==2) { complete=false; break; }
    if(complete) {
        for(size_t i=0;i<width;++i) if(flags[i]==1) {
            if(stop_requested()) { complete=false; break; }
            bool fallback=false; Hit h;
            if(predicate(low+i,d1[i],&h,&fallback)!=1) {
                if(stop_requested()) { complete=false; break; }
                die("positive replay mismatch");
            }
            push_hit(s,h);
        }
        if(stop_requested()) complete=false;
        if(complete) s->frontier=high+1;
    }
    if(!complete) s->nhit=saved_hits;
    free(residual); free(d1); free(flags);
    return complete;
}

static void read_seal(const char *dir,uint64_t id,char out[65]) {
    char name[32],path[MAX_PATH],buf[80];
    state_name(name,id,true); path2(path,dir,name);
    FILE *f=fopen(path,"r");
    if(!f) sysdie("open segment checksum");
    if(!fgets(buf,sizeof buf,f)||strlen(buf)!=65||buf[64]!='\n') {
        if(ferror(f)) sysdie("read segment checksum");
        die("segment checksum shape");
    }
    buf[64]=0;
    if(!valid_hash(buf)) die("segment checksum record");
    expect_eof(f,"segment checksum record");
    memcpy(out,buf,65);
    if(fclose(f)) sysdie("close checksum");
}
static void seal_segment(const char *dir,const Segment *s) {
    if(s->frontier!=s->high+1) die("attempt to seal incomplete segment");
    char name[32],path[MAX_PATH],sha[65],tmp[MAX_PATH];
    state_name(name,s->id,false); path2(path,dir,name); hash_file(path,sha);
    state_name(name,s->id,true); path2(path,dir,name);
    if(exists(path)) {
        char old[65]; read_seal(dir,s->id,old);
        if(strcmp(old,sha)) die("sealed segment checksum changed");
        return;
    }
    FILE *f; atomic_begin(&f,tmp,dir,name);
    if(fprintf(f,"%s\n",sha)<0) sysdie("write checksum");
    atomic_end(f,tmp,dir,name);
}
static void check_seal(const char *dir,uint64_t id) {
    char name[32],path[MAX_PATH],actual[65],expected[65];
    state_name(name,id,false); path2(path,dir,name); hash_file(path,actual);
    read_seal(dir,id,expected);
    if(strcmp(actual,expected)) die("segment checksum mismatch");
}
static bool equal_record(const char *line,const char *expected) {
    size_t n=strlen(expected);
    return n>0 && expected[n-1]=='\n' && strlen(line)==n-1 &&
           !memcmp(line,expected,n-1);
}
static void compare_line(FILE *f,const char *expected,const char *what) {
    char *line=NULL; size_t cap=0;
    bool good=read_line(f,&line,&cap) && equal_record(line,expected);
    free(line);
    if(!good) die(what);
}
static void compare_prefix_line(FILE *f,const char *expected,bool *ended,
                                const char *what) {
    if(*ended) return;
    char *line=NULL; size_t cap=0;
    if(!read_line(f,&line,&cap)) { *ended=true; free(line); return; }
    bool good=equal_record(line,expected);
    free(line);
    if(!good) die(what);
}
/* The sealed segment stream, not the aggregate tables, is authoritative. */
static void aggregate(const char *dir,const Config *c,uint64_t sealed,bool write) {
    FILE *mf=NULL,*hf=NULL;
    char mt[MAX_PATH],ht[MAX_PATH],mp[MAX_PATH],hp[MAX_PATH];
    char mh[128],hh[128];
    int mhn=snprintf(mh,sizeof mh,"A348425-MANIFEST-1\tcfg_sha=%s\n",
                     c->cfg_hash);
    int hhn=snprintf(hh,sizeof hh,"A348425-HITS-1\tcfg_sha=%s\n",
                     c->cfg_hash);
    if(mhn<0||mhn>=(int)sizeof mh||hhn<0||hhn>=(int)sizeof hh)
        die("aggregate header overflow");
    if(write) {
        atomic_begin(&mf,mt,dir,"index.tsv");
        atomic_begin(&hf,ht,dir,"hits.tsv");
        if(fputs(mh,mf)==EOF||fputs(hh,hf)==EOF||
           fputs("id\tlow\thigh\tstate_sha\telapsed_ns\thits\n",mf)==EOF ||
           fputs("r\tn\tx\ty\tR\n",hf)==EOF)
            sysdie("write aggregate header");
    } else {
        path2(mp,dir,"index.tsv"); path2(hp,dir,"hits.tsv");
        mf=fopen(mp,"r"); hf=fopen(hp,"r");
        if(!mf||!hf) sysdie("open aggregate");
        compare_line(mf,mh,"manifest config identity mismatch");
        compare_line(hf,hh,"hits config identity mismatch");
        compare_line(mf,"id\tlow\thigh\tstate_sha\telapsed_ns\thits\n",
                     "manifest header mismatch");
        compare_line(hf,"r\tn\tx\ty\tR\n","hits header mismatch");
    }
    for(uint64_t id=0;id<sealed;++id) {
        Segment s={0}; if(!read_seg(dir,c,id,&s)) die("missing sealed segment");
        if(s.frontier!=s.high+1) die("sealed segment incomplete");
        check_seal(dir,id);
        char name[32],path[MAX_PATH],sha[65],row[256];
        state_name(name,id,false); path2(path,dir,name); hash_file(path,sha);
        int n=snprintf(row,sizeof row,"%04" PRIx64 "\t%" PRIu64
                       "\t%" PRIu64 "\t%s\t%" PRIu64 "\t%zu\n",
                       id,s.low,s.high,sha,s.elapsed_ns,s.nhit);
        if(n<0||n>=(int)sizeof row) die("manifest text overflow");
        if(write) { if(fputs(row,mf)==EOF) sysdie("write manifest"); }
        else compare_line(mf,row,"manifest row mismatch");
        for(size_t j=0;j<s.nhit;++j) {
            hit_text(&s.hits[j],row);
            if(write) { if(fputs(row,hf)==EOF) sysdie("write hits"); }
            else compare_line(hf,row,"hits row mismatch");
        }
        free_seg(&s);
    }
    if(write) {
        atomic_end(mf,mt,dir,"index.tsv");
        atomic_end(hf,ht,dir,"hits.tsv");
    } else {
        expect_eof(mf,"extra/corrupt aggregate data");
        expect_eof(hf,"extra/corrupt aggregate data");
        if(fclose(mf)||fclose(hf)) sysdie("close aggregate");
    }
}
static void check_aggregate_identity(const char *dir,const Config *c) {
    char path[MAX_PATH],expected[128];
    const char *files[2]={"index.tsv","hits.tsv"};
    const char *magic[2]={"A348425-MANIFEST-1","A348425-HITS-1"};
    for(unsigned j=0;j<2;++j) {
        path2(path,dir,files[j]);
        FILE *f=fopen(path,"r");
        if(!f) {
            if(errno==ENOENT) continue; /* Derived absence; audit precedes rebuild. */
            sysdie("open aggregate identity");
        }
        int n=snprintf(expected,sizeof expected,"%s\tcfg_sha=%s\n",
                       magic[j],c->cfg_hash);
        if(n<0||n>=(int)sizeof expected) die("aggregate identity text");
        compare_line(f,expected,"aggregate config identity mismatch");
        if(fclose(f)) sysdie("close aggregate identity");
    }
}
/* Atomic table replacement may leave one or both tables at a valid earlier
   prefix after a crash. Missing derived files are repairable independently;
   every surviving file must still be an exact prefix. Changed rows are fatal. */
static bool check_aggregate_prefix(const char *dir,const Config *c,
                                   uint64_t sealed) {
    char mp[MAX_PATH],hp[MAX_PATH],mh[128],hh[128],row[256];
    path2(mp,dir,"index.tsv"); path2(hp,dir,"hits.tsv");
    FILE *mf=fopen(mp,"r");
    if(!mf&&errno!=ENOENT)sysdie("open manifest prefix");
    FILE *hf=fopen(hp,"r");
    if(!hf&&errno!=ENOENT)sysdie("open hits prefix");
    snprintf(mh,sizeof mh,"A348425-MANIFEST-1\tcfg_sha=%s\n",c->cfg_hash);
    snprintf(hh,sizeof hh,"A348425-HITS-1\tcfg_sha=%s\n",c->cfg_hash);
    if(mf) {
        compare_line(mf,mh,"manifest config identity mismatch");
        compare_line(mf,"id\tlow\thigh\tstate_sha\telapsed_ns\thits\n",
                     "manifest header mismatch");
    }
    if(hf) {
        compare_line(hf,hh,"hits config identity mismatch");
        compare_line(hf,"r\tn\tx\ty\tR\n","hits header mismatch");
    }
    bool me=mf==NULL,he=hf==NULL;
    for(uint64_t id=0;id<sealed;++id) {
        Segment s={0};
        if(!read_seg(dir,c,id,&s)||s.frontier!=s.high+1)
            die("aggregate prefix segment missing");
        char name[32],path[MAX_PATH],sha[65];
        state_name(name,id,false); path2(path,dir,name); hash_file(path,sha);
        int n=snprintf(row,sizeof row,"%04" PRIx64 "\t%" PRIu64
                       "\t%" PRIu64 "\t%s\t%" PRIu64 "\t%zu\n",
                       id,s.low,s.high,sha,s.elapsed_ns,s.nhit);
        if(n<0||n>=(int)sizeof row) die("manifest prefix text");
        compare_prefix_line(mf,row,&me,"manifest prefix corruption");
        for(size_t j=0;j<s.nhit;++j) {
            hit_text(&s.hits[j],row);
            compare_prefix_line(hf,row,&he,"hits prefix corruption");
        }
        free_seg(&s);
    }
    if(mf) {
        expect_eof(mf,"extra aggregate row");
        if(fclose(mf))sysdie("close manifest prefix");
    }
    if(hf) {
        expect_eof(hf,"extra aggregate row");
        if(fclose(hf))sysdie("close hits prefix");
    }
    return me||he;
}
static uint64_t parse_seg_filename(const char *name,bool *recognized) {
    *recognized=false;
    if(name[0]!='s'||strlen(name)<9) return 0;
    for(int i=1;i<=4;++i)
        if(!isxdigit((unsigned char)name[i]) ||
           (name[i]>='A'&&name[i]<='F')) return 0;
    if(strcmp(name+5,".tsv")&&strcmp(name+5,".sha256")) return 0;
    char temp[5]; memcpy(temp,name+1,4); temp[4]=0;
    *recognized=true;
    return strtoull(temp,NULL,16);
}
static bool program_temp_name(const char *name) {
    const char *mark=strstr(name,".tmp.");
    if(!mark||!mark[5]) return false;
    for(const char *p=mark+5;*p;++p)
        if(*p<'0'||*p>'9') return false;
    size_t len=(size_t)(mark-name);
    if((len==7&&!memcmp(name,"run.cfg",7))||
       (len==9&&!memcmp(name,"index.tsv",9))||
       (len==8&&!memcmp(name,"hits.tsv",8))) return true;
    if(len>=32) return false;
    char base[32]; memcpy(base,name,len); base[len]=0;
    bool recognized=false;
    (void)parse_seg_filename(base,&recognized);
    return recognized;
}
static void cleanup_program_temps(const char *dir) {
    DIR *d=opendir(dir);
    if(!d) sysdie("open run directory for cleanup");
    bool removed=false;
    for(;;) {
        errno=0;
        struct dirent *e=readdir(d);
        if(!e) {
            if(errno) sysdie("read run directory for cleanup");
            break;
        }
        if(!program_temp_name(e->d_name)) continue;
        char path[MAX_PATH]; path2(path,dir,e->d_name);
        if(unlink(path)) {
            if(errno!=ENOENT) sysdie("remove stale temporary file");
        } else removed=true;
    }
    if(closedir(d)) sysdie("close run directory after cleanup");
    if(removed) sync_dir(dir);
}
typedef struct {
    uint64_t sealed, sealed_frontier, frontier, hits;
    u128 elapsed_ns;
    bool partial;
    Segment open;
} Audit;
static Audit audit(const char *dir,const Config *c,bool check_hits) {
    Audit a={0}; a.frontier=c->start; a.sealed_frontier=c->start;
    uint64_t count=num_segments(c);
    for(uint64_t id=0;id<count;++id) {
        Segment s={0};
        if(!read_seg(dir,c,id,&s)) break;
        if(s.frontier<a.frontier) die("segment frontier went backwards");
        if(id>0) {
            uint64_t expected_low;
            uint64_t unused;
            seg_bounds(c,id,&expected_low,&unused);
            if(expected_low!=a.frontier) die("segment gap/overlap");
        }
        if(check_hits)
            for(size_t j=0;j<s.nhit;++j) {
                if(stop_requested()) exit(2);
                if(!verified_hit(&s.hits[j])) {
                    if(stop_requested()) exit(2);
                    die("hit witness mismatch");
                }
            }
        char name[32],path[MAX_PATH]; state_name(name,id,true);
        path2(path,dir,name);
        bool sealed=exists(path);
        if(sealed) {
            if(s.frontier!=s.high+1) die("premature segment seal");
            check_seal(dir,id);
            a.sealed++;
            a.sealed_frontier=s.high+1;
        } else {
            a.partial=true;
            a.open=s;
        }
        a.frontier=s.frontier;
        if(UINT64_MAX-a.hits<s.nhit) die("hit count overflow");
        a.hits+=s.nhit;
        a.elapsed_ns+=s.elapsed_ns;
        if(!sealed) break;
        free_seg(&s);
    }
    DIR *d=opendir(dir);
    if(!d) sysdie("open run directory");
    for(;;) {
        errno=0;
        struct dirent *e=readdir(d);
        if(!e) {
            if(errno) sysdie("read run directory");
            break;
        }
        bool recognized=false;
        uint64_t id=parse_seg_filename(e->d_name,&recognized);
        if(!recognized&&strcmp(e->d_name,".")&&strcmp(e->d_name,"..")&&
           strcmp(e->d_name,"run.cfg")&&strcmp(e->d_name,"index.tsv")&&
           strcmp(e->d_name,"hits.tsv")&&!program_temp_name(e->d_name))
            die("unexpected run directory entry");
        if(recognized && (id>=count ||
           id>=a.sealed+(a.partial?UINT64_C(1):UINT64_C(0))))
            die("orphan/future segment file");
    }
    if(closedir(d)) sysdie("close run directory");
    return a;
}
static int lock_run(const char *dir,bool exclusive) {
    char path[MAX_PATH]; path2(path,dir,"run.cfg");
    int fd=open(path,O_RDONLY);
    if(fd<0) sysdie("open run lock");
    if(flock(fd,(exclusive?LOCK_EX:LOCK_SH)|LOCK_NB)) {
        int saved=errno;
        if(close(fd)) sysdie("close run lock");
        if(saved==EWOULDBLOCK) die("run busy: another command holds run lock");
        errno=saved; sysdie("acquire run lock");
    }
    return fd;
}
static void do_init(int argc,char **argv) {
    if(argc!=8) die("usage: a348425 init DIR START END BLOCK SEGMENTS THREADS");
    Config c={0};
    if(!dec64(argv[3],&c.start)||!dec64(argv[4],&c.end)||
       !dec64(argv[5],&c.block)||!dec64(argv[6],&c.group)||
       !dec64(argv[7],&c.threads)) die("invalid decimal CLI argument");
    if(c.end<c.start||c.end>CAP||
       c.block<MIN_BLOCK||c.block>MAX_BLOCK||
       (c.block&(c.block-1))||c.group<1||
       c.group>MAX_SEGMENTS||c.group>(c.end-c.start)/c.block+1||
       c.threads<1||c.threads>MAX_THREADS)
        die("CLI outside certified configuration domain");
    (void)num_segments(&c);
    /* Reserve the longest generated basename and every future PID suffix. */
    char probe[MAX_PATH];
    int pn=snprintf(probe,sizeof probe,"%s/s0000.sha256.tmp.%ld",
                    argv[2],LONG_MAX);
    if(pn<0||pn>=MAX_PATH) die("run directory path too long");
    own_identity(c.src_hash,c.make_hash,c.bin_hash);
    if(mkdir(argv[2],0700)) sysdie("create new run directory");
    char parent[MAX_PATH]; path2(parent,argv[2],"..");
    sync_dir(parent);
    write_cfg(argv[2],&c);
    char cfgpath[MAX_PATH]; path2(cfgpath,argv[2],"run.cfg");
    hash_file(cfgpath,c.cfg_hash);
    aggregate(argv[2],&c,0,true);
    printf("initialized [%llu,%llu], block=%llu segments_requested=%llu threads=%llu "
           "segments=%llu cfg_sha=%s\n",
           (unsigned long long)c.start,(unsigned long long)c.end,
           (unsigned long long)c.block,(unsigned long long)c.group,
           (unsigned long long)c.threads,(unsigned long long)num_segments(&c),
           c.cfg_hash);
}
static void do_status(const char *dir,bool verify) {
    int lock=lock_run(dir,false);
    Config c={0}; config_load(dir,&c); check_identity(&c);
    Audit a=audit(dir,&c,verify);
    if(check_aggregate_prefix(dir,&c,a.sealed)) {
        fprintf(stderr,"REPAIRABLE: derived aggregate missing or valid short prefix; "
                "run next to rebuild it\n");
        exit(2);
    }
    char elapsed[40]; fmt128(a.elapsed_ns,elapsed);
    printf("A348425 %s: target=[%" PRIu64 ",%" PRIu64
           "] sealed_segments=%" PRIu64 " sealed_next=%" PRIu64
           " committed_next=%" PRIu64
           " remaining=%" PRIu64 " hits=%" PRIu64
           " elapsed_ns=%s cfg_sha=%s bin_sha=%s\n",
           verify?"VERIFY":"STATUS",c.start,c.end,a.sealed,
           a.sealed_frontier,a.frontier,
           c.end+1-a.frontier,a.hits,elapsed,c.cfg_hash,c.bin_hash);
    if(a.partial) {
        printf("INCOMPLETE segment=%" PRIu64 " next_block=%" PRIu64
               " (unsealed state; only earlier sealed segments certify "
               "an aggregate interval)\n",
               a.open.id,a.open.frontier);
        free_seg(&a.open);
    } else if(a.frontier==c.end+1) {
        puts("COMPLETE");
    } else {
        printf("%s segment=%" PRIu64 " from=%" PRIu64 "\n",
               verify?"INCOMPLETE target; next":"NEXT",a.sealed,
               a.frontier);
    }
    if(verify && a.sealed_frontier<c.end+1) exit(2);
    if(close(lock)) sysdie("close run lock");
}
static void do_next(const char *dir) {
    int lock=lock_run(dir,true);
    Config c={0}; config_load(dir,&c); check_identity(&c);
    cleanup_program_temps(dir);
    check_aggregate_identity(dir,&c);
    Audit a=audit(dir,&c,true);
    (void)check_aggregate_prefix(dir,&c,a.sealed);
    /* Repair a crash after a seal but before both aggregate renames.
       Segment state and its checksum remain the authority. */
    aggregate(dir,&c,a.sealed,true);
    uint64_t id=a.sealed;
    if(id>=num_segments(&c)) {
        puts("COMPLETE: target already sealed");
        if(a.partial) die("unexpected partial after end");
        if(close(lock)) sysdie("close run lock");
        return;
    }
    Segment s={0};
    if(a.partial) s=a.open;
    else {
        s.id=id; seg_bounds(&c,id,&s.low,&s.high);
        s.frontier=s.low;
    }
    if(s.frontier==s.high+1) {
        seal_segment(dir,&s);
        aggregate(dir,&c,id+1,true);
        printf("CLOSED recovered segment=%" PRIu64 "\n",id);
        free_seg(&s);
        if(close(lock)) sysdie("close run lock");
        return;
    }
    fprintf(stderr,"START segment=%" PRIu64 " target=%" PRIu64
            " block=[%" PRIu64 ",%" PRIu64 "] build=%s\n",
            id,c.end,s.frontier,s.high,c.bin_hash);
    live_target=c.end; live_segment=id; live_cursor=s.frontier;
    live_begin=ns_now(); live_enabled=true;
    if(live_begin>UINT64_MAX-UINT64_C(30000000000)) die("heartbeat clock overflow");
    atomic_store_explicit(&next_note,live_begin+UINT64_C(30000000000),memory_order_relaxed);
    Primes pr=make_primes(s.high);
    uint64_t start=ns_now(), fallbacks=0, last_note=start;
    bool failed_block=false;
    while(s.frontier<=s.high&&!stop_requested()) {
        uint64_t low=s.frontier;
        u128 hi=(u128)low+c.block-1;
        if(hi>s.high) hi=s.high;
        live_cursor=s.frontier;
        bool complete=block_scan(&c,&pr,&s,low,(uint64_t)hi,&fallbacks);
        if(!complete) { failed_block=true; break; }
        uint64_t now=ns_now();
        if(now<start) die("monotonic clock wrapped");
        uint64_t dt=now-start;
        if(UINT64_MAX-s.elapsed_ns<dt) die("segment elapsed overflow");
        s.elapsed_ns+=dt;
        start=now;
        write_seg(dir,&c,&s);
        if(now-last_note>=UINT64_C(30000000000)||s.frontier==s.high+1) {
            double seconds=(double)s.elapsed_ns/1e9;
            double rate=seconds>0?(double)(s.frontier-s.low)/seconds:0;
            double eta=rate>0?(double)(s.high+1-s.frontier)/rate:0;
            fprintf(stderr,"PROGRESS segment=%" PRIu64
                    " committed_next=%" PRIu64 " tested=%" PRIu64
                    " hits=%zu elapsed_s=%.0f rate=%.1f/s eta_segment_s=%.0f fallbacks=%" PRIu64
                    "\n",id,s.frontier,s.frontier-s.low,s.nhit,
                    seconds,rate,eta,fallbacks);
            last_note=now;
        }
    }
    live_enabled=false;
    free(pr.v);
    if(s.frontier==s.high+1&&!stop_requested()) {
        seal_segment(dir,&s);
        aggregate(dir,&c,id+1,true);
        fprintf(stderr,"CLOSED segment=%" PRIu64 " committed_next=%" PRIu64
                " hits=%zu fallbacks=%" PRIu64 "\n",
                id,s.frontier,s.nhit,fallbacks);
    } else {
        fprintf(stderr,"INCOMPLETE segment=%" PRIu64
                " committed_next=%" PRIu64 " next_block=%" PRIu64
                " fallbacks=%" PRIu64 "\n",
                id,s.frontier,s.frontier,fallbacks);
    }
    free_seg(&s);
    if(close(lock)) sysdie("close run lock");
    if(stop_requested()||failed_block) exit(2);
}
static int dispatch(int argc,char **argv) {
    if(argc<2) die("usage: a348425 init|next|status|verify ...");
    if(!strcmp(argv[1],"init")) { do_init(argc,argv); return 0; }
    if(argc!=3) die("usage: a348425 next|status|verify DIR");
    if(!strcmp(argv[1],"next")) {
        struct sigaction sa={0}; sa.sa_handler=on_signal;
        sa.sa_flags=SA_RESTART;
        sigemptyset(&sa.sa_mask);
        if(sigaction(SIGINT,&sa,NULL)||sigaction(SIGTERM,&sa,NULL))
            sysdie("install signal handler");
        do_next(argv[2]); return 0;
    }
    if(!strcmp(argv[1],"status")) { do_status(argv[2],false); return 0; }
    if(!strcmp(argv[1],"verify")) { do_status(argv[2],true); return 0; }
    die("unknown mode");
    return 1;
}

int main(int argc,char **argv) {
    int status=dispatch(argc,argv);
    if(fflush(stdout)==EOF || ferror(stdout)) sysdie("flush stdout");
    if(fflush(stderr)==EOF || ferror(stderr)) sysdie("flush stderr");
    return status;
}
