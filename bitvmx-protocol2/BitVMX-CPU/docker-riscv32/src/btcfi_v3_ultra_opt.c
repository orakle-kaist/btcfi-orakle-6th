// BTCFi Option Registration v3 - Ultra Optimized for <1024 steps
// Target: 10-bit configuration (max 1024 steps)

// Stack in .bss
__attribute__((used, aligned(16), section(".bss")))
static unsigned char __stack_area[64 * 1024]; // Reduced stack
asm(".globl __stack_top\n"
    ".equ __stack_top, __stack_area + (64 * 1024)\n");

// Entry point
__asm__(
    ".section .text.entry\n"
    ".global _start\n"
    "_start:\n"
    "    la sp, __stack_top\n"
    "    call main\n"
    "_hang:\n"
    "    j _hang\n"
);

// Use linker-provided symbols instead of hardcoded addresses
extern volatile unsigned char __input_start[];
extern volatile unsigned char __output_start[];

#define INPUT_PTR   ((volatile unsigned char*)__input_start)
#define OUTPUT_PTR  ((volatile unsigned char*)__output_start)

// Create .input section
__attribute__((section(".input"), used, aligned(16)))
unsigned char input_buffer[256] = {0};  // Smaller buffer

// Create .output section
__attribute__((section(".output"), used, aligned(16)))
unsigned char output_buffer[256] = {0};  // Output buffer

typedef unsigned int uint32_t;
typedef unsigned long long uint64_t;
typedef long long int64_t;

// Minimal structures - only what we need
typedef struct {
    uint32_t option_type;       // 0=Call, 1=Put
    uint32_t _pad1;
    uint64_t strike_price;      // cents
    uint64_t spot_price;        // cents  
    uint64_t size_sats;         // satoshis requested
    uint64_t available_liq;     // available liquidity
    uint32_t oracle_count;
    uint32_t _pad2;
    uint64_t oracle_prices[3];  // 3 oracle prices
} OptionInput;

typedef struct {
    uint32_t result;            // 1=approved, 0=rejected
    uint32_t reason;            // rejection reason if any
    uint64_t accepted_size;     // actual size accepted
    uint64_t collateral;        // required collateral
} OptionOutput;

// Constants
#define MIN_STRIKE 100000ULL
#define MAX_STRIKE 50000000000ULL
#define MIN_SIZE 10000ULL
#define MAX_SIZE 10000000000ULL
#define MAX_DEVIATION_BPS 200ULL
#define FLOOR_PERCENT 80ULL

// Fast abs for int64
static inline uint64_t abs64(int64_t x) {
    return (x < 0) ? (uint64_t)(-x) : (uint64_t)x;
}

// Ultra-simple division for common cases
static inline uint64_t div_by_100(uint64_t x) {
    // Compiler optimizes this to multiplication by reciprocal
    return x / 100ULL;
}

static inline uint64_t div_by_10000(uint64_t x) {
    return x / 10000ULL;
}

// Minimal memset
static void simple_memset(void* s, int c, unsigned n) {
    unsigned char* p = (unsigned char*)s;
    for (unsigned i = 0; i < n; i++) p[i] = (unsigned char)c;
}

int main(void) {
    // Read input
    OptionInput in;
    volatile const unsigned char* ip = INPUT_PTR;
    unsigned char* dp = (unsigned char*)&in;
    for (unsigned i = 0; i < sizeof(OptionInput); i++) {
        dp[i] = ip[i];
    }
    
    // Initialize output
    OptionOutput out;
    simple_memset(&out, 0, sizeof(out));
    
    // === EARLY EXIT CHECKS (minimal operations) ===
    
    // 1. Option type check
    if (in.option_type > 1) {
        out.reason = 1;
        goto write_output;
    }
    
    // 2. Strike price check  
    if (in.strike_price < MIN_STRIKE || in.strike_price > MAX_STRIKE) {
        out.reason = 2;
        goto write_output;
    }
    
    // 3. Size check
    if (in.size_sats < MIN_SIZE || in.size_sats > MAX_SIZE) {
        out.reason = 3;
        goto write_output;
    }
    
    // 4. Oracle validation - OPTIMIZED (no division)
    if (in.oracle_count != 3) {
        out.reason = 7;
        goto write_output;
    }
    
    // Calculate average (simple for 3 values)
    uint64_t p0 = in.oracle_prices[0];
    uint64_t p1 = in.oracle_prices[1];
    uint64_t p2 = in.oracle_prices[2];
    uint64_t avg = (p0 + p1 + p2) / 3ULL;
    
    if (avg == 0) {
        out.reason = 8;
        goto write_output;
    }
    
    // Check deviations using CROSS-MULTIPLICATION (no division!)
    // Instead of: deviation * 10000 / avg > MAX_DEVIATION_BPS
    // We check: deviation * 10000 > MAX_DEVIATION_BPS * avg
    uint64_t max_allowed = MAX_DEVIATION_BPS * avg;
    
    uint64_t dev0 = abs64((int64_t)p0 - (int64_t)avg) * 10000ULL;
    uint64_t dev1 = abs64((int64_t)p1 - (int64_t)avg) * 10000ULL;
    uint64_t dev2 = abs64((int64_t)p2 - (int64_t)avg) * 10000ULL;
    
    if (dev0 > max_allowed || dev1 > max_allowed || dev2 > max_allowed) {
        out.reason = 8;
        goto write_output;
    }
    
    // === MAIN LOGIC (simplified) ===
    
    // 5. Determine accepted size (simple min)
    uint64_t accepted = in.size_sats;
    if (accepted > in.available_liq) {
        accepted = in.available_liq;
    }
    
    if (accepted < MIN_SIZE) {
        out.reason = 5;
        goto write_output;
    }
    
    // 6. Calculate collateral (simplified)
    if (in.option_type == 0) {
        // Call: collateral = size
        out.collateral = accepted;
    } else {
        // Put: simplified calculation
        // Use conservative floor = 80% of spot
        uint64_t floor = div_by_100(in.spot_price * FLOOR_PERCENT);
        if (floor == 0) floor = 1; // Prevent division by zero
        
        // Collateral = (strike / floor) * size
        // But to avoid 64-bit division, we use approximation
        // If strike < floor: ratio = 1
        // If strike >= floor: use simple ratio
        if (in.strike_price < floor) {
            out.collateral = accepted;
        } else if (in.strike_price < floor * 2) {
            out.collateral = accepted * 2;
        } else if (in.strike_price < floor * 3) {
            out.collateral = accepted * 3;
        } else {
            // Cap at 4x for safety
            out.collateral = accepted * 4;
        }
    }
    
    // 7. Success!
    out.result = 1;
    out.accepted_size = accepted;
    
write_output:
    // Write output
    volatile unsigned char* op = OUTPUT_PTR;
    const unsigned char* sp = (const unsigned char*)&out;
    for (unsigned i = 0; i < sizeof(OptionOutput); i++) {
        op[i] = sp[i];
    }
    
    // Memory fence
    __asm__ __volatile__("" ::: "memory");
    
    return out.result;
}