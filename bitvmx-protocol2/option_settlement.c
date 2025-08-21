#include <stdint.h>

// Option settlement program for BitVMX
// Input format: 16 bytes (4 x 32-bit words)
// - word 0: option_type (0=Call, 1=Put)
// - word 1: strike_price (USD cents)
// - word 2: spot_price (USD cents)
// - word 3: quantity (units x 100)

// Function to calculate option payoff
uint32_t calculate_payoff(uint32_t option_type, uint32_t strike, uint32_t spot, uint32_t quantity) {
    uint32_t payoff = 0;
    
    if (option_type == 0) {
        // Call option: max(spot - strike, 0)
        if (spot > strike) {
            payoff = ((spot - strike) * quantity) / 100;
        }
    } else if (option_type == 1) {
        // Put option: max(strike - spot, 0)
        if (strike > spot) {
            payoff = ((strike - spot) * quantity) / 100;
        }
    }
    
    return payoff;
}

int main() {
    // Read input from BitVMX
    uint32_t input[4];
    
    // BitVMX provides input through memory-mapped I/O
    // The input is read from a specific memory location
    volatile uint32_t* input_ptr = (volatile uint32_t*)0x10000000;
    
    for (int i = 0; i < 4; i++) {
        input[i] = input_ptr[i];
    }
    
    uint32_t option_type = input[0];
    uint32_t strike_price = input[1];
    uint32_t spot_price = input[2];
    uint32_t quantity = input[3];
    
    // Calculate payoff
    uint32_t payoff = calculate_payoff(option_type, strike_price, spot_price, quantity);
    
    // Write result to output
    volatile uint32_t* output_ptr = (volatile uint32_t*)0x10001000;
    output_ptr[0] = payoff;
    
    // Also write to standard locations for debugging
    output_ptr[1] = option_type;
    output_ptr[2] = strike_price;
    output_ptr[3] = spot_price;
    output_ptr[4] = quantity;
    
    // Return payoff as exit code (limited to 255)
    return payoff > 255 ? 255 : payoff;
}