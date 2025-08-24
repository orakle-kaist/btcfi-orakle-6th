// BTCFi Option Registration for BitVMX - Optimized Version
// Maintains core functionality with reduced computational steps

// Entry point for bare metal RISC-V
__asm__(
    ".section .text.entry\n"
    ".global _start\n"
    "_start:\n"
    "    li sp, 0xE0800000\n"      // Set stack pointer
    "    call main\n"              
    "    li a0, 0\n"               
    "    li a7, 93\n"              
    "    ecall\n"                  
);

// Allocate space for input section
__attribute__((section(".input"))) unsigned char input_buffer[4096] = {0};

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

// BitVMX memory addresses
#define INPUT_ADDRESS 0x80000000
#define OUTPUT_ADDRESS 0x80001000

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

// Pool State
typedef struct {
    uint64_t total_liquidity;       
    uint64_t available_liquidity;   
    int64_t call_delta_exposure;    
    int64_t put_delta_exposure;     
    int64_t net_delta;              
    uint64_t total_premium_collected;
    uint32_t max_delta_ratio_bps;   
} __attribute__((packed)) BTCFiPoolState;

// Option Registration Input
typedef struct {
    uint32_t option_type;           // 0=Call, 1=Put
    uint64_t strike_price;          // USD cents
    uint64_t expiry_timestamp;      
    uint64_t max_size;              // Maximum size in satoshis
    BTCFiPoolState pool_state;      
    uint64_t current_spot_price;    
    uint64_t base_premium_rate;     
    int64_t option_delta;           
    uint32_t oracle_count;          
    uint8_t oracle_hashes[3][8];    
    uint8_t aggregator_hash[32];    
} __attribute__((packed)) BTCFiOptionInput;

// Option Registration Output
typedef struct {
    uint8_t option_id[32];          
    uint32_t validation_result;     
    uint32_t liquidity_check;       
    uint32_t delta_check;           
    uint32_t parameter_check;       
    int64_t new_pool_delta;         
    uint32_t delta_ratio_after_bps; 
    uint64_t required_collateral;   
    uint8_t registration_hash[32];  
    uint64_t creation_timestamp;    
    uint32_t risk_level;            
} __attribute__((packed)) BTCFiOptionOutput;

// Constants
#define MIN_STRIKE_PRICE 100000       
#define MAX_STRIKE_PRICE 1000000000   
#define MIN_QUANTITY 100000           
#define MAX_QUANTITY 1000000000       
#define COLLATERAL_RATIO 110          

// Simplified hash for option ID generation
void simple_hash(const uint8_t* input, unsigned long len, uint8_t* output) {
    uint32_t hash = 0x6a09e667;
    
    // Process only key bytes to reduce iterations
    for (unsigned long i = 0; i < len && i < 64; i += 4) {
        hash ^= *((uint32_t*)(input + i));
        hash = ((hash << 5) | (hash >> 27)) + 0x9e3779b9;
    }
    
    // Fill output
    for (int i = 0; i < 32; i += 4) {
        *((uint32_t*)(output + i)) = hash + i;
    }
}

// Validate basic option parameters
uint32_t validate_parameters(const BTCFiOptionInput* input) {
    // Combined validation to reduce branches
    if (input->option_type > 1 ||
        input->strike_price < MIN_STRIKE_PRICE || 
        input->strike_price > MAX_STRIKE_PRICE ||
        input->max_size < MIN_QUANTITY || 
        input->max_size > MAX_QUANTITY ||
        input->oracle_count != 3) {
        return 0;
    }
    return 1;
}

// Check pool liquidity
uint32_t check_pool_liquidity(const BTCFiOptionInput* input, uint64_t* required_collateral) {
    // Calculate required collateral based on option type
    if (input->option_type == 0) { // Call
        *required_collateral = input->max_size;
    } else { // Put
        *required_collateral = (input->strike_price * input->max_size) / 100000000;
    }
    
    // Apply collateral ratio
    *required_collateral = (*required_collateral * COLLATERAL_RATIO) / 100;
    
    // Check if pool has enough
    return input->pool_state.available_liquidity >= *required_collateral ? 1 : 0;
}

// Check delta limits
uint32_t check_delta_limits(const BTCFiOptionInput* input, int64_t* new_delta, uint32_t* ratio_after) {
    // Calculate new pool delta
    if (input->option_type == 0) { // Call
        *new_delta = input->pool_state.call_delta_exposure + input->option_delta;
    } else { // Put
        *new_delta = input->pool_state.put_delta_exposure - input->option_delta;
    }
    
    // Calculate delta ratio (simplified)
    if (input->pool_state.total_liquidity > 0) {
        uint64_t abs_delta = (*new_delta < 0) ? -(*new_delta) : *new_delta;
        *ratio_after = (abs_delta * 10000) / input->pool_state.total_liquidity;
    } else {
        *ratio_after = 0;
    }
    
    // Check limit
    return *ratio_after <= input->pool_state.max_delta_ratio_bps ? 1 : 0;
}

int main(int argc) {
    BTCFiOptionInput* input = (BTCFiOptionInput*)INPUT_ADDRESS;
    BTCFiOptionOutput output;
    
    memset(&output, 0, sizeof(output));
    
    // 1. Validate parameters
    output.parameter_check = validate_parameters(input);
    
    // 2. Check pool liquidity
    uint64_t required_collateral = 0;
    output.liquidity_check = check_pool_liquidity(input, &required_collateral);
    output.required_collateral = required_collateral;
    
    // 3. Check delta limits
    int64_t new_delta = 0;
    uint32_t ratio_after = 0;
    output.delta_check = check_delta_limits(input, &new_delta, &ratio_after);
    output.new_pool_delta = new_delta;
    output.delta_ratio_after_bps = ratio_after;
    
    // Overall validation
    output.validation_result = output.parameter_check && 
                              output.liquidity_check && 
                              output.delta_check;
    
    if (output.validation_result) {
        // Generate option ID
        simple_hash((uint8_t*)input, sizeof(BTCFiOptionInput), output.option_id);
        
        // Set metadata
        output.creation_timestamp = input->expiry_timestamp - (30 * 24 * 3600);
        simple_hash((uint8_t*)input, 32, output.registration_hash);
        
        // Assess risk level
        if (ratio_after > 1500) {
            output.risk_level = 3;
        } else if (ratio_after > 1000) {
            output.risk_level = 2;
        } else {
            output.risk_level = 1;
        }
    }
    
    // Copy output to BitVMX output address
    uint8_t* output_addr = (uint8_t*)OUTPUT_ADDRESS;
    uint8_t* output_ptr = (uint8_t*)&output;
    for (int i = 0; i < sizeof(BTCFiOptionOutput); i++) {
        output_addr[i] = output_ptr[i];
    }
    
    return output.validation_result;
}