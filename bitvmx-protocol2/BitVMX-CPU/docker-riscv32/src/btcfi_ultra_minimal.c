// Ultra-minimal BTCFi Option Registration (final <20 steps)
// - real stack in ELF (.noinit)
// - .input/.output LOAD sections
// - no loops/div/64-bit helpers

typedef unsigned int u32;

// Tiny stack in ELF (no zero-init)
__attribute__((section(".noinit"), aligned(16), used))
static unsigned char __stack_area[1024];
asm(".globl __stack_top\n"
    ".equ __stack_top, __stack_area + 1024\n");

// Startup: set SP, GP -> call main -> HALT
__asm__(
  ".section .text.entry\n"
  ".global _start\n"
  "_start:\n"
  "  la   sp, __stack_top\n"
  "  la   gp, __global_pointer$\n"  // ✅ GP initialization added
  "  call main\n"
  "  ebreak\n"                      // Halt execution after main
);

// Input from host (4 words)
__attribute__((section(".input"), aligned(16), used))
volatile u32 input_data[4] = {0};

// Output to host (2 words)
__attribute__((section(".output"), aligned(16), used))
volatile u32 output_data[2] = {0};

int main(void) {
  // Option registration logic:
  // input[0] = option_type (0=Call, 1=Put)  
  // input[1] = strike_price
  // input[2] = size
  // input[3] = spot_price
  
  // Simple validation
  if (input_data[0] > 1) {
    output_data[0] = 0; // rejected
    output_data[1] = 1; // invalid type
    return 0;
  }
  
  if (input_data[1] < 1000 || input_data[1] > 500000) {
    output_data[0] = 0; // rejected
    output_data[1] = 2; // invalid strike
    return 0;
  }
  
  // Approved
  output_data[0] = 1; // approved
  output_data[1] = input_data[2]; // accepted size
  return 1;
}
