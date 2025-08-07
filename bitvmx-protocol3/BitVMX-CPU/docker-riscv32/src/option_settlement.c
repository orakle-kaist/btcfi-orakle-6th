#include <stdint.h>

// Option settlement calculation for BitVMX
// Input: option_type (0=Call, 1=Put), strike_price, spot_price, quantity
// Output: payout in cents (USD * 100)

typedef struct {
    uint32_t option_type;    // 0=Call, 1=Put
    uint32_t strike_price;   // USD * 100 (cents)
    uint32_t spot_price;     // USD * 100
    uint32_t quantity;       // unit * 100
} OptionInput;

int main() {
    // Read input from memory (passed by emulator)
    OptionInput* input = (OptionInput*)0x80000000;
    
    uint32_t option_type = input->option_type;
    uint32_t strike = input->strike_price;
    uint32_t spot = input->spot_price;
    uint32_t quantity = input->quantity;
    
    uint32_t payout = 0;
    
    if (option_type == 0) {
        // Call option: max(0, spot - strike) * quantity
        if (spot > strike) {
            payout = ((spot - strike) * quantity) / 100;
        }
    } else {
        // Put option: max(0, strike - spot) * quantity
        if (strike > spot) {
            payout = ((strike - spot) * quantity) / 100;
        }
    }
    
    // Return payout as exit code
    return payout;
}