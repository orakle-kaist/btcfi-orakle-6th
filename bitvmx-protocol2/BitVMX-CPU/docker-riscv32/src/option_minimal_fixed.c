// Minimal option registration - matching program_fixed_exit.elf structure
// Text at 0x0, very small code

__attribute__((section(".input")))
volatile unsigned int input_buffer[4];  // Only 16 bytes like original

__attribute__((section(".registers")))  
volatile unsigned int registers[16];    // 64 bytes at 0xF0000000

__asm__(
    ".section .text\n"
    ".global _start\n"
    "_start:\n"
    "  li sp, 0xE0001000\n"
    "  call main\n"
    "  li a0, 0\n"
    "  li s1, 0x5d0\n"
    "  ebreak\n"
);

int main(void) {
    // Minimal option registration logic
    volatile unsigned int *in = (volatile unsigned int *)0xAA000000;
    volatile unsigned int *out = (volatile unsigned int *)0xF0000000;
    
    // Read input: option_type, strike, expiry, pool_size
    unsigned int type = in[0];
    unsigned int strike = in[1];
    unsigned int expiry = in[2];
    unsigned int pool = in[3];
    
    // Simple validation - keep it minimal
    unsigned int ok = 1;
    if (type > 1) ok = 0;
    if (strike < 1000) ok = 0;
    if (strike > 500000) ok = 0;
    
    // Write minimal output
    out[0] = ok;
    out[1] = type;
    out[2] = strike;
    out[3] = pool;
    out[4] = expiry;
    out[5] = ok ? pool : 0;  // Required liquidity
    out[6] = type ^ strike;  // Simple hash
    out[7] = 0x6757;         // Magic number from original
    
    return 0;
}