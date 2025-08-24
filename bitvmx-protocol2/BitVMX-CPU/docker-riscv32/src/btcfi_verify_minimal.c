// Ultra-minimal BTCFi verification
// Target: <50 steps for BitVMX

// Entry point
__asm__(
    ".section .text.entry\n"
    ".global _start\n"
    "_start:\n"
    "    li sp, 0x80100000\n"
    "    call main\n"
    "_hang:\n"
    "    j _hang\n"
);

// Allocate input section
__attribute__((section(".input"), used, aligned(16)))
unsigned char input_buffer[256] = {0};

#define INPUT_ADDRESS ((unsigned int*)0xAA000000)
#define OUTPUT_ADDRESS ((unsigned int*)0xAA001000)

int main() {
    unsigned int payout = INPUT_ADDRESS[0];    // Payout amount
    unsigned int expected = INPUT_ADDRESS[1];  // Expected hash
    unsigned int actual = INPUT_ADDRESS[2];    // Actual hash
    
    // Simple verification
    if (expected == actual) {
        OUTPUT_ADDRESS[0] = payout;  // Valid
        OUTPUT_ADDRESS[1] = 1;        // Success
    } else {
        OUTPUT_ADDRESS[0] = 0;        // Invalid
        OUTPUT_ADDRESS[1] = 0;        // Fail
    }
    
    return 0;
}