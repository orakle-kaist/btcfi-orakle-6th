/* BTCFi Option Settlement Program */
#include <stdint.h>

// Option types
#define CALL_OPTION 0
#define PUT_OPTION  1

// Simple option settlement calculation
int calculate_settlement(uint32_t option_type, uint32_t strike_price, uint32_t spot_price) {
    if (option_type == CALL_OPTION) {
        // Call option: profit if spot > strike
        if (spot_price > strike_price) {
            return spot_price - strike_price;
        }
    } else if (option_type == PUT_OPTION) {
        // Put option: profit if spot < strike
        if (spot_price < strike_price) {
            return strike_price - spot_price;
        }
    }
    return 0; // Out of the money
}

int main() {
    // Test case: Call option, Strike $50k, Spot $52k
    uint32_t option_type = CALL_OPTION;
    uint32_t strike = 50000;
    uint32_t spot = 52000;
    
    int profit = calculate_settlement(option_type, strike, spot);
    
    // Output result (for BitVMX verification)
    if (profit > 0) {
        // In the money - return profit
        return profit;
    } else {
        // Out of the money
        return 0;
    }
}