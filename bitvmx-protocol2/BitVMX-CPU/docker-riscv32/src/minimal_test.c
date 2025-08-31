// Ultra minimal test - just return immediately
__asm__(
  ".section .text.entry\n"
  ".global _start\n"
  "_start:\n"
  "  li a0, 42\n"     // return value 42
  "  ebreak\n"        // halt
);

int main(void) {
    return 0;
}