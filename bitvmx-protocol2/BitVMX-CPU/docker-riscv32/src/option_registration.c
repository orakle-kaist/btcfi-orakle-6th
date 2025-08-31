// BTCFi Option Registration for BitVMX - Proper Implementation
// Following BitVMX memory map: 0xAA000000 for input, 0xE0800000 for stack

// Entry point with proper stack setup
__asm__(
    ".section .text.entry\n"
    ".global _start\n"
    "_start:\n"
    "    lui sp, 0xE0800\n"      // Stack top at 0xE0800000
    "    call main\n"
    "    li a7, 93\n"            // exit syscall
    "    ecall\n"
);

// Input at 0xAA000000 - BitVMX standard
__attribute__((section(".input"), aligned(4)))
volatile unsigned char input_buffer[4096] = {0};

// Simple types
typedef unsigned int uint32_t;
typedef unsigned long long uint64_t;

// Option Input Structure
typedef struct __attribute__((packed)) {
    uint32_t option_type;       // 0=Call, 1=Put
    uint64_t strike_price;      // Strike in USD cents
    uint64_t spot_price;        // Current spot in USD cents
    uint64_t quantity;          // Option size in sats
    uint64_t pool_liquidity;    // Available pool liquidity
} OptionInput;

// Option Output Structure  
typedef struct __attribute__((packed)) {
    uint32_t approved;          // 1=approved, 0=rejected
    uint64_t premium;           // Premium in sats
    uint64_t collateral;        // Required collateral
    uint32_t commitment;        // 32-bit commitment hash
} OptionOutput;

// Simple memory copy
void* my_memcpy(void* dest, const void* src, unsigned int n) {
    char* d = (char*)dest;
    const char* s = (const char*)src;
    while (n--) *d++ = *s++;
    return dest;
}

// Simple 64-bit division (for BitVMX without stdlib)
uint64_t __udivdi3(uint64_t dividend, uint64_t divisor) {
    if (divisor == 0) return 0;
    if (dividend < divisor) return 0;
    
    uint64_t quotient = 0;
    uint64_t temp = 0;
    
    for (int i = 63; i >= 0; i--) {
        temp = (temp << 1) | ((dividend >> i) & 1);
        if (temp >= divisor) {
            temp -= divisor;
            quotient |= (1ULL << i);
        }
    }
    return quotient;
}

// Calculate premium (simplified)
uint64_t calculate_premium(uint32_t option_type, uint64_t strike, uint64_t spot, uint64_t quantity) {
    // Base premium: 2% of notional
    uint64_t base_premium = quantity / 50;
    
    // Adjust for moneyness
    if (option_type == 0) { // Call
        if (spot > strike) {
            // ITM call - add intrinsic value
            uint64_t intrinsic = ((spot - strike) * quantity) / spot;
            base_premium += intrinsic;
        }
    } else { // Put
        if (strike > spot) {
            // ITM put - add intrinsic value
            uint64_t intrinsic = ((strike - spot) * quantity) / spot;
            base_premium += intrinsic;
        }
    }
    
    return base_premium;
}

// Simple hash for commitment
uint32_t generate_commitment(uint32_t type, uint64_t strike, uint64_t spot) {
    // Simple hash: XOR and rotate
    uint32_t hash = type;
    hash ^= (uint32_t)(strike >> 32);
    hash ^= (uint32_t)(strike & 0xFFFFFFFF);
    hash ^= (uint32_t)(spot >> 32);
    hash ^= (uint32_t)(spot & 0xFFFFFFFF);
    
    // Rotate left by 13
    hash = (hash << 13) | (hash >> 19);
    hash ^= 0x5BD1E995;
    
    return hash;
}

int main() {
    // Read input from 0xAA000000
    OptionInput input;
    volatile uint32_t* input_ptr = (volatile uint32_t*)0xAA000000;
    
    // Read option data
    input.option_type = input_ptr[0];
    input.strike_price = ((uint64_t)input_ptr[1] << 32) | input_ptr[2];
    input.spot_price = ((uint64_t)input_ptr[3] << 32) | input_ptr[4];
    input.quantity = ((uint64_t)input_ptr[5] << 32) | input_ptr[6];
    input.pool_liquidity = ((uint64_t)input_ptr[7] << 32) | input_ptr[8];
    
    // Prepare output
    OptionOutput output;
    
    // Validate inputs
    if (input.option_type > 1) {
        output.approved = 0;
        output.premium = 0;
        output.collateral = 0;
        output.commitment = 0;
    } else if (input.quantity == 0 || input.quantity > input.pool_liquidity) {
        output.approved = 0;
        output.premium = 0;
        output.collateral = 0;
        output.commitment = 0;
    } else {
        // Calculate premium
        output.premium = calculate_premium(
            input.option_type,
            input.strike_price, 
            input.spot_price,
            input.quantity
        );
        
        // Set collateral (for simplicity, same as quantity)
        output.collateral = input.quantity;
        
        // Generate commitment
        output.commitment = generate_commitment(
            input.option_type,
            input.strike_price,
            input.spot_price
        );
        
        // Approve
        output.approved = 1;
    }
    
    // Write output to 0xAA001000 
    volatile uint32_t* output_ptr = (volatile uint32_t*)0xAA001000;
    output_ptr[0] = output.approved;
    output_ptr[1] = (uint32_t)(output.premium >> 32);
    output_ptr[2] = (uint32_t)(output.premium & 0xFFFFFFFF);
    output_ptr[3] = (uint32_t)(output.collateral >> 32);
    output_ptr[4] = (uint32_t)(output.collateral & 0xFFFFFFFF);
    output_ptr[5] = output.commitment;
    
    return 0;
}