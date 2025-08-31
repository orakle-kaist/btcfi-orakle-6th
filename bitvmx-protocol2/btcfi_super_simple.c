// BTCFi super simple - direct halt with ebreak
typedef unsigned int u32;

// Small stack
__attribute__((section(".noinit"), aligned(16), used))
static unsigned char stack[512];

// Entry with immediate ebreak after main
__asm__(
  ".section .text.entry\n"
  ".global _start\n"
  "_start:\n"
  "  la   sp, stack + 512\n"
  "  call main\n"
  "  ebreak\n"
);

// Input/output sections  
__attribute__((section(".input"), used))
volatile u32 INPUT[4] = {0};

__attribute__((section(".output"), used))
volatile u32 OUTPUT[2] = {0};

int main(void) {
  // Super simple logic
  if (INPUT[0] == INPUT[1]) {
    OUTPUT[0] = 1;  // success
    OUTPUT[1] = INPUT[2];  // payout
  } else {
    OUTPUT[0] = 0;  // fail
    OUTPUT[1] = 0;
  }
  return OUTPUT[0];
}