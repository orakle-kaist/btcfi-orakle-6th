// Ultra minimal - exactly like program_fixed_exit structure
// No loops, no complex logic

__attribute__((section(".input")))
volatile unsigned int input_buffer[4];

__attribute__((section(".registers")))  
volatile unsigned int registers[16];

__asm__(
    ".section .text\n"
    ".global _start\n"
    "_start:\n"
    "  li sp, 0xE0001000\n"
    "  auipc ra, 0\n"
    "  jalr 20(ra)\n"    // Jump to main at offset 0x14
    "  li a0, 0\n"
    "  li s1, 0x5d0\n"
    "  ecall\n"
    "main:\n"
    "  lui t0, 0xAA000\n"       // Input address
    "  lw a0, 0(t0)\n"          // Load option_type
    "  lw a1, 4(t0)\n"          // Load strike
    "  lw a2, 8(t0)\n"          // Load expiry
    "  lw a3, 12(t0)\n"         // Load pool
    "  lui t1, 0xF0000\n"       // Output address
    "  li t2, 1\n"              // ok = 1
    "  sw t2, 0(t1)\n"          // Store ok
    "  sw a0, 4(t1)\n"          // Store option_type
    "  sw a1, 8(t1)\n"          // Store strike
    "  sw a3, 12(t1)\n"         // Store pool
    "  sw a2, 16(t1)\n"         // Store expiry
    "  sw a3, 20(t1)\n"         // Store liquidity
    "  xor t3, a0, a1\n"        // type ^ strike
    "  sw t3, 24(t1)\n"         // Store hash
    "  li t4, 0x6757\n"         // Magic number
    "  sw t4, 28(t1)\n"         // Store magic
    "  ret\n"
);