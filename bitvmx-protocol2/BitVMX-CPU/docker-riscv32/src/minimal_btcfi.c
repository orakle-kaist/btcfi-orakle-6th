// Minimal BTCFi for BitVMX - Target: <100 steps
#include <stdint.h>

#define INPUT_ADDRESS 0xAA000000
#define OUTPUT_ADDRESS 0xAA001000

// No stack, no function calls, minimal instructions
int main() {
    uint32_t* in = (uint32_t*)INPUT_ADDRESS;
    uint32_t* out = (uint32_t*)OUTPUT_ADDRESS;
    
    // Read only 3 values: spot, strike, type
    uint32_t spot = in[0];    
    uint32_t strike = in[1];
    uint32_t type = in[2];
    
    // Ultra-simple ITM check (no division, no multiplication)
    if (type == 0) {  // Call
        if (spot > strike) {
            out[0] = 1;  // ITM
        } else {
            out[0] = 0;  // OTM
        }
    } else {  // Put
        if (strike > spot) {
            out[0] = 1;  // ITM
        } else {
            out[0] = 0;  // OTM
        }
    }
    
    return 0;
}