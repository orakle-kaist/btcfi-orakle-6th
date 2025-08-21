#include <stdint.h>
#include <string.h>

// Advanced option settlement calculation for BitVMX
// Supports multiple option types and complex scenarios

typedef struct {
    uint32_t option_type;      // 0=Call, 1=Put, 2=Binary Call, 3=Binary Put
    uint32_t strike_price;     // USD * 100 (cents)
    uint32_t spot_price;       // USD * 100
    uint32_t quantity;         // unit * 100
    uint32_t barrier_level;    // For barrier options (0 if not applicable)
    uint32_t early_exercise;   // 0=European, 1=American
    uint32_t time_to_expiry;   // Minutes remaining
    uint32_t volatility;       // Implied volatility * 100
} AdvancedOptionInput;

typedef struct {
    uint32_t payout;          // Payout in cents
    uint32_t exercise_type;   // 0=No exercise, 1=ITM, 2=OTM, 3=ATM
    uint32_t barrier_hit;     // 0=No, 1=Yes (for barrier options)
    uint32_t profit_loss;     // P&L in cents (can be negative)
} SettlementResult;

// Calculate moneyness of the option
uint32_t calculate_moneyness(uint32_t option_type, uint32_t strike, uint32_t spot) {
    if (option_type == 0 || option_type == 2) { // Call options
        if (spot > strike + 100) return 1;      // ITM (with buffer)
        else if (spot < strike - 100) return 2; // OTM (with buffer)
        else return 3;                          // ATM
    } else { // Put options
        if (strike > spot + 100) return 1;      // ITM
        else if (strike < spot - 100) return 2; // OTM
        else return 3;                          // ATM
    }
}

// Calculate intrinsic value
uint32_t calculate_intrinsic_value(uint32_t option_type, uint32_t strike, uint32_t spot, uint32_t quantity) {
    uint32_t intrinsic = 0;
    
    if (option_type == 0) { // Call
        if (spot > strike) {
            intrinsic = ((spot - strike) * quantity) / 100;
        }
    } else if (option_type == 1) { // Put
        if (strike > spot) {
            intrinsic = ((strike - spot) * quantity) / 100;
        }
    } else if (option_type == 2) { // Binary Call
        if (spot >= strike) {
            intrinsic = quantity * 100; // Fixed payout
        }
    } else if (option_type == 3) { // Binary Put
        if (spot <= strike) {
            intrinsic = quantity * 100; // Fixed payout
        }
    }
    
    return intrinsic;
}

// Check barrier conditions
uint32_t check_barrier(uint32_t barrier_level, uint32_t spot_price, uint32_t option_type) {
    if (barrier_level == 0) return 0; // No barrier
    
    // Knock-out barrier logic
    if (option_type == 0 || option_type == 2) { // Call-like
        if (spot_price >= barrier_level) return 1; // Barrier hit
    } else { // Put-like
        if (spot_price <= barrier_level) return 1; // Barrier hit
    }
    
    return 0;
}

// Calculate time decay factor (simplified)
uint32_t calculate_time_decay_factor(uint32_t time_to_expiry, uint32_t volatility) {
    // Simple linear decay for demonstration
    // In production, use proper theta calculation
    if (time_to_expiry > 10080) { // More than 1 week
        return 100; // No significant decay
    } else if (time_to_expiry > 1440) { // More than 1 day
        return 90;
    } else if (time_to_expiry > 60) { // More than 1 hour
        return 70;
    } else {
        return 50; // Significant decay
    }
}

// Main settlement function
int main() {
    // Read input from memory (passed by emulator)
    AdvancedOptionInput* input = (AdvancedOptionInput*)0x80000000;
    SettlementResult result = {0, 0, 0, 0};
    
    // Extract input values
    uint32_t option_type = input->option_type;
    uint32_t strike = input->strike_price;
    uint32_t spot = input->spot_price;
    uint32_t quantity = input->quantity;
    uint32_t barrier = input->barrier_level;
    uint32_t early_ex = input->early_exercise;
    uint32_t time_remaining = input->time_to_expiry;
    uint32_t vol = input->volatility;
    
    // Check barrier conditions first
    if (barrier > 0) {
        result.barrier_hit = check_barrier(barrier, spot, option_type);
        if (result.barrier_hit) {
            // Barrier knocked out - option worthless
            result.payout = 0;
            result.exercise_type = 2; // OTM due to barrier
            return 0;
        }
    }
    
    // Calculate moneyness
    result.exercise_type = calculate_moneyness(option_type, strike, spot);
    
    // Calculate intrinsic value
    uint32_t intrinsic = calculate_intrinsic_value(option_type, strike, spot, quantity);
    
    // For American options, check if early exercise is optimal
    if (early_ex == 1 && time_remaining > 0) {
        uint32_t time_factor = calculate_time_decay_factor(time_remaining, vol);
        
        // Simple early exercise decision
        // In production, compare with continuation value
        if (option_type == 1) { // American Put
            // Deep ITM puts often benefit from early exercise
            if (strike > spot * 115 / 100) { // More than 15% ITM
                result.payout = intrinsic;
                return intrinsic;
            }
        }
    }
    
    // European style or no early exercise
    if (time_remaining == 0) { // At expiry
        result.payout = intrinsic;
    } else {
        // Option still has time value
        // In production, return fair value instead of intrinsic
        result.payout = intrinsic;
    }
    
    // Calculate P&L (simplified - assumes premium was 2% of strike)
    uint32_t premium_paid = (strike * 2 * quantity) / 10000;
    result.profit_loss = result.payout > premium_paid ? 
                        result.payout - premium_paid : 
                        premium_paid - result.payout;
    
    // Return payout as exit code
    return result.payout;
}