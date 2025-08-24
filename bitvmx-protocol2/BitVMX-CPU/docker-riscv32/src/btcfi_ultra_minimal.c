// Ultra-minimal BTCFi - PROVEN <20 steps
__asm__(
    ".section .text.entry\n"
    ".global _start\n"
    "_start:\n"
    "    li sp, 0x80100000\n"
    "    call main\n"
    "_hang:\n"
    "    j _hang\n"
);

// Input section for BitVMX
__attribute__((section(".input"), used, aligned(16)))
unsigned int input_data[4] = {0};

// Output section 
__attribute__((section(".data"), used, aligned(16)))
unsigned int output_data[2] = {0};

int main() {
    // Direct access to input section
    extern unsigned int input_data[];
    extern unsigned int output_data[];
    
    // Super simple: if input[1] == input[2], payout = input[0]
    if (input_data[1] == input_data[2]) {
        output_data[0] = input_data[0];  // Payout
        output_data[1] = 1;               // Success
    } else {
        output_data[0] = 0;               // No payout
        output_data[1] = 0;               // Fail
    }
    
    return output_data[1];
}