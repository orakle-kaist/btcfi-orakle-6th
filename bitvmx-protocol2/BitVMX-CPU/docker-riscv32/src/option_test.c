// Test with exact same pattern as program_fixed_exit

__attribute__((section(".input")))
volatile unsigned int input_buffer[4];

__attribute__((section(".registers")))  
volatile unsigned int regs_out[16];

// Copy exact assembly pattern from working elf
__asm__(
    ".section .text\n"
    ".global _start\n"
    "_start:\n"
    "  lui sp, 0xE0001\n"
    "  auipc ra, 0\n"
    "  jalr 20(ra)\n"    
    "  li a0, 0\n"
    "  .word 0x05d00893\n"  // Same as working elf
    "  ecall\n"
    "main:\n"
    "  lui a5, 0xAA000\n"
    "  mv a5, a5\n"
    "  lw a1, 0(a5)\n"     // option_type
    "  lw a4, 4(a5)\n"     // strike
    "  lw a3, 8(a5)\n"     // expiry  
    "  lw a2, 12(a5)\n"    // pool
    "  lui a5, 0xF0000\n"
    "  mv a5, a5\n"
    "  li a0, 1\n"         // ok = 1
    "  sw a0, 0(a5)\n"
    "  li a0, 100\n"       // Test value
    "  sw a0, 4(a5)\n"
    "  sw a1, 8(a5)\n"     // option_type
    "  sw a4, 12(a5)\n"    // strike
    "  sw a3, 16(a5)\n"    // expiry
    "  sw a2, 20(a5)\n"    // pool
    "  add a4, a4, a3\n"   // strike + expiry
    "  sw a4, 24(a5)\n"
    "  lui a4, 0x5\n"
    "  addi a4, a4, 0x678\n"
    "  sw a4, 28(a5)\n"
    "  li a0, 0\n"
    "  ret\n"
);