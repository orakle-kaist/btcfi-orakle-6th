// Minimal BTCFi Option Registration for BitVMX
// Ultra-optimized version with minimal steps

__asm__(
    ".section .text.entry\n"
    ".global _start\n"
    "_start:\n"
    "    li sp, 0xE0800000\n"
    "    call main\n"              
    "    li a0, 0\n"               
    "    li a7, 93\n"              
    "    ecall\n"                  
);

#define INPUT_ADDRESS 0x80000000
#define OUTPUT_ADDRESS 0x80001000

typedef unsigned int uint32_t;

// Minimal validation - just check option type
int main() {
    uint32_t* input = (uint32_t*)INPUT_ADDRESS;
    uint32_t* output = (uint32_t*)OUTPUT_ADDRESS;
    
    // Read option type (0=Call, 1=Put)
    uint32_t option_type = input[0];
    
    // Simple validation
    uint32_t valid = (option_type <= 1) ? 1 : 0;
    
    // Write result
    output[0] = valid;
    output[1] = option_type;
    output[2] = 0x12345678; // Simple hash
    
    return valid;
}