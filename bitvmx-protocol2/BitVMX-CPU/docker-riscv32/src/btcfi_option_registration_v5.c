// BTCFi Option Registration for BitVMX - Version 5 (Ultra-lean)
// - Proper HALT (no ebreak trap loop)
// - No memcpy/memset loops
// - No 64-bit division loops (reciprocal multiply)
// - Direct MMIO IO (4 words)

typedef unsigned int      uint32_t;
typedef unsigned long long uint64_t;
typedef int                int32_t;

// ========== BitVMX MMIO ==========
#define INPUT_ADDR   ((volatile uint32_t*)0xAA000000)  // 4 words
#define OUTPUT_ADDR  ((volatile uint32_t*)0xAA001000)  // 4 words
#define HALT_ADDR    ((volatile uint32_t*)0xAA00FFF8)  // write 1 to stop

// ========== Stack (.noinit) & Entry ==========
__attribute__((used, aligned(16), section(".noinit")))
static unsigned char __stack_area[8 * 1024]; // 8KB is enough

asm(".globl __stack_top\n"
    ".equ __stack_top, __stack_area + (8 * 1024)\n");

// Macro helpers for stringification
#define XSTR(x) STR(x)
#define STR(x) #x

__asm__(
    ".section .text.entry\n"
    ".global _start\n"
    "_start:\n"
    "  la sp, __stack_top\n"
    "  call main\n"
    "  li t0, 0xAA00FFF8\n"   // HALT address
    "  li t1, 1\n"
    "  sw t1, 0(t0)\n"
    "1: wfi\n"                // Wait (minimal step increase)
    "   j 1b\n"
);

// ========== Input/Output Simple Model ==========
typedef struct {
  uint32_t option_type;        // 0=Call, 1=Put
  uint32_t strike_price;       // USD
  uint32_t max_size;           // sats
  uint32_t spot_price;         // USD
} In;

typedef struct {
  uint32_t ok;                 // 1=approved,0=rejected
  uint32_t reason;             // 0 if ok
  uint32_t accepted_size;      // sats
  uint32_t required_collateral;// sats
} Out;

// ========== Manual CLZ Implementation ==========
static inline int manual_clz(uint32_t x) {
  if (x == 0) return 32;
  int n = 0;
  if (x <= 0x0000FFFF) { n += 16; x <<= 16; }
  if (x <= 0x00FFFFFF) { n += 8;  x <<= 8; }
  if (x <= 0x0FFFFFFF) { n += 4;  x <<= 4; }
  if (x <= 0x3FFFFFFF) { n += 2;  x <<= 2; }
  if (x <= 0x7FFFFFFF) { n += 1; }
  return n;
}

// ========== Fast Reciprocal (Q30) Based Division Elimination ==========
// spot ∈ [1..1_000_000] assumed. reciprocal ≈ floor((1<<30)/spot)
// 2 Newton corrections sufficient for accuracy, only 2 iterations (fixed) + mul only
static inline uint32_t q30_recip(uint32_t d) {
  // Defense against zero
  if (d == 0) return 0xFFFFFFFFu;
  
  // Count leading zeros manually
  int lz = manual_clz(d);
  uint32_t n = 31 - lz;                    // Effective bits-1
  uint32_t d_norm = d << (31 - n);         // Normalize to [2^30..2^31)
  
  // Initial guess (Q30): simple linear approximation
  uint64_t g = ((uint64_t)3<<30) - ((uint64_t)d_norm>>1);

  // Newton iteration 2 times: g = g*(2 - d*g) ; Q30 scale management
  for (int i=0; i<2; i++){
    uint64_t dg = ((uint64_t)d * g) >> 30;        // Q30
    uint64_t two_minus_dg = (2ull<<30) - dg;      // Q30
    g = (g * two_minus_dg) >> 30;                 // Q30
  }
  
  // Denormalization correction
  if (n > 0) g >>= n; else g <<= (-n);
  return (uint32_t)g; // Q30 reciprocal
}

// (a*b)/d ≈ ( (a*b) * recip(d) ) >> 30  (mul only)
static inline uint32_t fast_div_mul(uint32_t a, uint32_t b, uint32_t d){
  uint64_t prod = (uint64_t)a * (uint64_t)b;      // 64b
  uint32_t rcp  = q30_recip(d);                   // Q30
  uint64_t t    = (prod * rcp) >> 30;
  return (t > 0xFFFFFFFFull) ? 0xFFFFFFFFu : (uint32_t)t;
}

// ========== Policy Constants ==========
#define MIN_STRIKE  1000
#define MAX_STRIKE  500000
#define MIN_SIZE    10000
#define MAX_SIZE    100000000

// ========== Main ==========
int main(void){
  // Direct read from MMIO 4 words
  In in;
  in.option_type  = INPUT_ADDR[0];
  in.strike_price = INPUT_ADDR[1];
  in.max_size     = INPUT_ADDR[2];
  in.spot_price   = INPUT_ADDR[3];

  Out out = {0,0,0,0};

  // Validation (branches only, no loops)
  if (in.option_type > 1) { 
    out.reason = 1; 
    goto done; 
  }
  if (in.strike_price < MIN_STRIKE || in.strike_price > MAX_STRIKE) { 
    out.reason = 2; 
    goto done; 
  }
  if (in.max_size < MIN_SIZE || in.max_size > MAX_SIZE) { 
    out.reason = 3; 
    goto done; 
  }

  // Accepted size: constant min (no loops)
  uint32_t cap1 = 50000000u, cap2 = 10000000u;
  uint32_t acc = in.max_size;
  if (cap1 < acc) acc = cap1;
  if (cap2 < acc) acc = cap2;
  out.accepted_size = acc;

  // Collateral: Call = size, Put = (strike*size)/spot via fast path
  if (in.option_type == 0){
    out.required_collateral = acc;
  } else {
    // (strike * size)/spot → multiply + reciprocal (fixed 2 corrections)
    out.required_collateral = fast_div_mul(in.strike_price, acc, in.spot_price);
  }

  out.ok = 1;

done:
  // Direct write 4 words result
  OUTPUT_ADDR[0] = out.ok;
  OUTPUT_ADDR[1] = out.reason;
  OUTPUT_ADDR[2] = out.accepted_size;
  OUTPUT_ADDR[3] = out.required_collateral;
  
  // Signal halt to BitVMX
  *HALT_ADDR = 1;
  
  return out.ok;
}