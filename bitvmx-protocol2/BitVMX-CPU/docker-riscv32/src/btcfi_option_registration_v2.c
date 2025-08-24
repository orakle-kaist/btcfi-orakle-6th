// BTCFi Option Registration for BitVMX - Version 2
// Improved with proper validation, collateral calculation, and safety checks

// Allocate stack memory in .bss section (128KB)
__attribute__((used, aligned(16), section(".bss")))
static unsigned char __stack_area[128 * 1024];

// Define __stack_top symbol at the end of stack array
asm(".globl __stack_top\n"
    ".equ __stack_top, __stack_area + (128 * 1024)\n");

// Entry point for bare metal RISC-V
__asm__(
    ".section .text.entry\n"
    ".global _start\n"
    "_start:\n"
    "    la sp, __stack_top\n"     // Use actual stack memory in ELF
    "    call main\n"              
    "_hang:\n"                     // Infinite loop for BitVMX
    "    j _hang\n"           
);

// Allocate space for input section - must be in a loadable section
__attribute__((section(".input"), used, aligned(16))) 
unsigned char input_buffer[4096] = {0};

typedef unsigned char uint8_t;
typedef unsigned short uint16_t;
typedef unsigned int uint32_t;
typedef unsigned long long uint64_t;
typedef long long int64_t;

// Minimal memory operations
void* memset(void* s, int c, unsigned long n) {
    char* p = (char*)s;
    for (unsigned long i = 0; i < n; i++) {
        p[i] = c;
    }
    return s;
}

// BitVMX memory addresses - match linker script
#define INPUT_ADDRESS ((volatile uint8_t*)0xAA000000)
#define OUTPUT_ADDRESS ((volatile uint8_t*)0xAA001000)

// Manual 64-bit division for bare metal
uint64_t __udivdi3(uint64_t dividend, uint64_t divisor) {
    if (divisor == 0) return 0;
    if (dividend < divisor) return 0;
    
    uint64_t quotient = 0;
    uint64_t remainder = 0;
    
    for (int i = 63; i >= 0; i--) {
        remainder = (remainder << 1) | ((dividend >> i) & 1);
        if (remainder >= divisor) {
            remainder -= divisor;
            quotient |= (1ULL << i);
        }
    }
    
    return quotient;
}

// Pool State - aligned structure
typedef struct {
    uint64_t total_liquidity;       
    uint64_t available_liquidity;   
    int64_t net_delta;              // Combined delta exposure
    uint64_t total_premium_collected;
    uint32_t max_delta_ratio_bps;   // Maximum delta ratio in basis points (e.g., 2000 = 20%)
} BTCFiPoolState;

// Option Registration Input - aligned structure
typedef struct {
    uint32_t option_type;           // 0=Call, 1=Put
    uint32_t _pad1;                 // Padding for alignment
    uint64_t strike_price;          // USD cents
    uint64_t expiry_timestamp;      
    uint64_t current_timestamp;     // NEW: Current time for validation
    uint64_t max_size;              // Maximum size in satoshis
    uint64_t current_spot_price;    // Current BTC price in USD cents
    uint64_t base_premium_rate;     // Base premium in basis points
    int64_t option_delta_per_btc;   // Delta per 1 BTC of the option
    uint64_t implied_volatility;    // IV in basis points (e.g., 5000 = 50%)
    BTCFiPoolState pool_state;      
    uint32_t oracle_count;          
    uint32_t _pad2;                 // Padding
    uint64_t oracle_timestamps[3];  // NEW: Oracle timestamps for freshness check
    uint64_t oracle_prices[3];      // NEW: Individual oracle prices
} BTCFiOptionInput;

// Option Registration Output - aligned structure  
typedef struct {
    uint32_t validation_result;     // 1=approved, 0=rejected
    uint32_t rejection_reason;      // NEW: Specific reason code if rejected
    uint64_t accepted_size;         // NEW: Actual accepted size (may be less than requested)
    uint64_t required_collateral;   // Required collateral in satoshis
    uint64_t premium_amount;        // NEW: Calculated premium in satoshis
    int64_t new_pool_delta;         // Pool delta after this option
    uint32_t delta_ratio_after_bps; // Delta ratio after registration
    uint32_t risk_level;            // Risk assessment (1=low, 2=medium, 3=high)
    uint64_t effective_timestamp;   // NEW: Timestamp when registration is effective
} BTCFiOptionOutput;

// Constants
#define MIN_STRIKE_PRICE 100000        // $1
#define MAX_STRIKE_PRICE 50000000000   // $500,000
#define MIN_QUANTITY 10000             // 0.0001 BTC
#define MAX_QUANTITY 10000000000       // 100 BTC
#define MIN_PREMIUM_BPS 10             // 0.1% minimum premium
#define MAX_ORACLE_AGE 300             // 5 minutes max oracle age
#define MAX_PRICE_DEVIATION_BPS 200    // 2% max price deviation between oracles
#define MIN_EXPIRY_TIME 3600           // Minimum 1 hour to expiry
#define MAX_EXPIRY_TIME 31536000       // Maximum 1 year to expiry
#define CONSERVATIVE_FACTOR 80         // 80% for conservative floor price

// Rejection reason codes
#define REJECT_INVALID_TYPE 1
#define REJECT_INVALID_STRIKE 2
#define REJECT_INVALID_SIZE 3
#define REJECT_INVALID_EXPIRY 4
#define REJECT_INSUFFICIENT_LIQUIDITY 5
#define REJECT_DELTA_LIMIT_EXCEEDED 6
#define REJECT_STALE_ORACLE 7
#define REJECT_ORACLE_DEVIATION 8
#define REJECT_PREMIUM_TOO_LOW 9
#define REJECT_INVALID_VOLATILITY 10

// Helper: Get minimum of three values
uint64_t min3(uint64_t a, uint64_t b, uint64_t c) {
    uint64_t min = a;
    if (b < min) min = b;
    if (c < min) min = c;
    return min;
}

// Helper: Get absolute value
uint64_t abs64(int64_t x) {
    return x < 0 ? -x : x;
}

// Validate oracle data freshness and consistency
uint32_t validate_oracles(const BTCFiOptionInput* input) {
    // Check oracle count
    if (input->oracle_count != 3) {
        return REJECT_STALE_ORACLE;
    }
    
    // Check freshness - all oracles must be recent
    for (int i = 0; i < 3; i++) {
        if (input->current_timestamp - input->oracle_timestamps[i] > MAX_ORACLE_AGE) {
            return REJECT_STALE_ORACLE;
        }
    }
    
    // Check price consistency - no oracle should deviate too much
    uint64_t avg_price = (input->oracle_prices[0] + input->oracle_prices[1] + input->oracle_prices[2]) / 3;
    for (int i = 0; i < 3; i++) {
        uint64_t deviation = abs64(input->oracle_prices[i] - avg_price);
        if (deviation * 10000 / avg_price > MAX_PRICE_DEVIATION_BPS) {
            return REJECT_ORACLE_DEVIATION;
        }
    }
    
    return 0; // No rejection
}

// Calculate conservative floor price for put collateral
uint64_t calculate_floor_price(uint64_t spot_price, uint64_t volatility_bps, uint64_t time_to_expiry) {
    // Simplified conservative estimate: floor = spot * conservative_factor
    // In production, use proper Black-Scholes or historical volatility
    uint64_t floor = (spot_price * CONSERVATIVE_FACTOR) / 100;
    
    // Further reduce based on volatility and time
    // Higher volatility or longer time = lower floor
    if (volatility_bps > 5000) { // >50% volatility
        floor = (floor * 90) / 100;
    }
    if (time_to_expiry > 30 * 24 * 3600) { // >30 days
        floor = (floor * 95) / 100;
    }
    
    return floor;
}

// Calculate premium based on risk factors
uint64_t calculate_premium(const BTCFiOptionInput* input, uint64_t accepted_size, int64_t new_delta) {
    // Base premium
    uint64_t premium = (accepted_size * input->base_premium_rate) / 10000;
    
    // Add delta risk premium
    uint64_t delta_risk = abs64(new_delta) * 10000 / input->pool_state.total_liquidity;
    premium += (accepted_size * delta_risk) / 100000;
    
    // Add time value premium (simplified)
    uint64_t time_to_expiry = input->expiry_timestamp - input->current_timestamp;
    if (time_to_expiry > 7 * 24 * 3600) { // More than 7 days
        premium = (premium * 110) / 100; // 10% extra for longer dated
    }
    
    // Add volatility premium
    if (input->implied_volatility > 5000) { // >50% IV
        premium = (premium * 120) / 100; // 20% extra for high vol
    }
    
    // Enforce minimum premium
    uint64_t min_premium = (accepted_size * MIN_PREMIUM_BPS) / 10000;
    if (premium < min_premium) {
        premium = min_premium;
    }
    
    return premium;
}

int main(int argc) {
    // Read input from MMIO address
    BTCFiOptionInput input;
    volatile uint8_t* input_ptr = INPUT_ADDRESS;
    uint8_t* dest = (uint8_t*)&input;
    for (int i = 0; i < sizeof(BTCFiOptionInput); i++) {
        dest[i] = input_ptr[i];
    }
    
    BTCFiOptionOutput output;
    memset(&output, 0, sizeof(output));
    
    // 1. Validate basic parameters
    if (input.option_type > 1) {
        output.rejection_reason = REJECT_INVALID_TYPE;
        goto finalize;
    }
    
    if (input.strike_price < MIN_STRIKE_PRICE || input.strike_price > MAX_STRIKE_PRICE) {
        output.rejection_reason = REJECT_INVALID_STRIKE;
        goto finalize;
    }
    
    if (input.max_size < MIN_QUANTITY || input.max_size > MAX_QUANTITY) {
        output.rejection_reason = REJECT_INVALID_SIZE;
        goto finalize;
    }
    
    // 2. Validate expiry
    uint64_t time_to_expiry = input.expiry_timestamp - input.current_timestamp;
    if (time_to_expiry < MIN_EXPIRY_TIME || time_to_expiry > MAX_EXPIRY_TIME) {
        output.rejection_reason = REJECT_INVALID_EXPIRY;
        goto finalize;
    }
    
    // 3. Validate oracles
    uint32_t oracle_reject = validate_oracles(&input);
    if (oracle_reject != 0) {
        output.rejection_reason = oracle_reject;
        goto finalize;
    }
    
    // 4. Calculate maximum acceptable size based on liquidity
    uint64_t cap_liquidity;
    if (input.option_type == 0) { // Call
        // For calls, we need BTC collateral
        cap_liquidity = input.pool_state.available_liquidity;
    } else { // Put
        // For puts, calculate based on conservative floor price
        uint64_t floor_price = calculate_floor_price(
            input.current_spot_price, 
            input.implied_volatility,
            time_to_expiry
        );
        // Required BTC = (Strike * Size) / Floor_Price
        // So max size = (Available_BTC * Floor_Price) / Strike
        cap_liquidity = (input.pool_state.available_liquidity * floor_price) / input.strike_price;
    }
    
    // 5. Calculate maximum acceptable size based on delta limits
    uint64_t cap_delta = MAX_QUANTITY; // Start with max
    if (input.pool_state.total_liquidity > 0) {
        // Calculate how much size we can accept before hitting delta limit
        int64_t current_delta = input.pool_state.net_delta;
        int64_t max_allowed_delta = (input.pool_state.total_liquidity * input.pool_state.max_delta_ratio_bps) / 10000;
        int64_t delta_room = max_allowed_delta - abs64(current_delta);
        if (delta_room > 0 && input.option_delta_per_btc != 0) {
            cap_delta = (delta_room * 100000000) / abs64(input.option_delta_per_btc);
        } else {
            cap_delta = 0;
        }
    }
    
    // 6. Determine accepted size
    output.accepted_size = min3(input.max_size, cap_liquidity, cap_delta);
    
    if (output.accepted_size < MIN_QUANTITY) {
        output.rejection_reason = REJECT_INSUFFICIENT_LIQUIDITY;
        goto finalize;
    }
    
    // 7. Calculate new pool delta
    int64_t delta_change = (input.option_delta_per_btc * output.accepted_size) / 100000000;
    output.new_pool_delta = input.pool_state.net_delta + delta_change;
    
    // 8. Verify delta limit not exceeded
    if (input.pool_state.total_liquidity > 0) {
        output.delta_ratio_after_bps = (abs64(output.new_pool_delta) * 10000) / input.pool_state.total_liquidity;
        if (output.delta_ratio_after_bps > input.pool_state.max_delta_ratio_bps) {
            output.rejection_reason = REJECT_DELTA_LIMIT_EXCEEDED;
            output.accepted_size = 0;
            goto finalize;
        }
    }
    
    // 9. Calculate required collateral
    if (input.option_type == 0) { // Call
        output.required_collateral = output.accepted_size;
    } else { // Put
        uint64_t floor_price = calculate_floor_price(
            input.current_spot_price,
            input.implied_volatility,
            time_to_expiry
        );
        output.required_collateral = (input.strike_price * output.accepted_size) / floor_price;
    }
    
    // 10. Calculate premium
    output.premium_amount = calculate_premium(&input, output.accepted_size, output.new_pool_delta);
    
    // 11. Set risk level
    if (output.delta_ratio_after_bps > 1500) {
        output.risk_level = 3; // High risk
    } else if (output.delta_ratio_after_bps > 1000) {
        output.risk_level = 2; // Medium risk
    } else {
        output.risk_level = 1; // Low risk
    }
    
    // 12. Set timestamps and approve
    output.effective_timestamp = input.current_timestamp;
    output.validation_result = 1; // Approved!
    
finalize:
    // Write output to MMIO address
    volatile uint8_t* output_addr = OUTPUT_ADDRESS;
    uint8_t* src = (uint8_t*)&output;
    for (int i = 0; i < sizeof(BTCFiOptionOutput); i++) {
        output_addr[i] = src[i];
    }
    
    return output.validation_result;
}