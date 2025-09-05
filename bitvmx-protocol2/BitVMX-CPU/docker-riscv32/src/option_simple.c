// Simple option registration for BitVMX
// Minimal code to avoid section issues

__attribute__((section(".input")))
volatile unsigned int input_buffer[64];

__attribute__((section(".output")))  
volatile unsigned int output_buffer[64];

__asm__(
    ".section .text.entry\n"
    ".global _start\n"
    "_start:\n"
    "  li sp, 0xE0001000\n"
    "  call main\n"
    "  ebreak\n"
);

int main(void) {
    // Read from 0xAA000000
    volatile unsigned int *input = (volatile unsigned int *)0xAA000000;
    volatile unsigned int *output = (volatile unsigned int *)0xAB000000;
    
    unsigned int option_type = input[0];  // 0=Call, 1=Put
    unsigned int strike = input[1];       // Strike price
    unsigned int expiry = input[2];       // Expiry time
    unsigned int pool_size = input[3];    // Pool size
    
    // Simple validation
    unsigned int ok = 1;
    if (option_type > 1) ok = 0;
    if (strike < 1000 || strike > 500000) ok = 0;
    if (pool_size < 10000000) ok = 0;
    
    // Write output
    output[0] = ok;
    output[1] = option_type;
    output[2] = strike;
    output[3] = pool_size;
    
    return 0;
}