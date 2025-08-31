// BTCFi Option Registration - BitVMX Compliant
// Memory Map: .text@0x80000000, .input@0xAA000000, .stack@0xE0000000-0xE0800000

// Stack allocation in .bss section (BitVMX standard)
__attribute__((section(".bss"), aligned(16)))
unsigned char __stack_area[0x800000];  // 8MB stack

// Define stack top symbol
__asm__(".global __stack_top\n"
        ".equ __stack_top, 0xE0800000\n");

// Entry point
__asm__(
    ".section .text\n"
    ".global _start\n"
    "_start:\n"
    "    li sp, 0xE0800000\n"    // Stack grows down from 0xE0800000
    "    call main\n"
    "    li a7, 93\n"             // exit syscall
    "    ecall\n"
);

// Input section at 0xAA000000 - make it larger to include output area
__attribute__((section(".input"), aligned(4)))
unsigned char input_section[8192] = {0};  // 8KB for input + output

// Types
typedef unsigned int uint32_t;
typedef unsigned long long uint64_t;

// 64-bit division helper
uint64_t __udivdi3(uint64_t n, uint64_t d) {
    if (d == 0) return 0;
    uint64_t q = 0, r = 0;
    for (int i = 63; i >= 0; i--) {
        r = (r << 1) | ((n >> i) & 1);
        if (r >= d) {
            r -= d;
            q |= (1ULL << i);
        }
    }
    return q;
}

int main() {
    // Read input from 0xAA000000
    volatile uint32_t* input = (volatile uint32_t*)0xAA000000;
    volatile uint32_t* output = (volatile uint32_t*)0xAA001000;
    
    // Parse option parameters
    uint32_t option_type = input[0];      // 0=Call, 1=Put
    uint64_t strike = ((uint64_t)input[1] << 32) | input[2];
    uint64_t spot = ((uint64_t)input[3] << 32) | input[4];
    uint64_t quantity = ((uint64_t)input[5] << 32) | input[6];
    
    // Validate
    uint32_t approved = 0;
    uint64_t premium = 0;
    uint32_t commitment = 0;
    
    if (option_type <= 1 && quantity > 0) {
        // Calculate premium (2% base)
        premium = quantity / 50;
        
        // Add intrinsic value
        if (option_type == 0) { // Call
            if (spot > strike) {
                uint64_t intrinsic = ((spot - strike) * quantity) / spot;
                premium += intrinsic;
            }
        } else { // Put
            if (strike > spot) {
                uint64_t intrinsic = ((strike - spot) * quantity) / spot;
                premium += intrinsic;
            }
        }
        
        // Generate commitment hash
        commitment = (option_type ^ (uint32_t)strike ^ (uint32_t)spot) * 0x9e3779b9;
        approved = 1;
    }
    
    // Write output
    output[0] = approved;
    output[1] = (uint32_t)(premium >> 32);
    output[2] = (uint32_t)(premium & 0xFFFFFFFF);
    output[3] = commitment;
    
    return 0;
}