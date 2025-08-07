#include <stdint.h>

typedef unsigned int size_t;

// Simple memcpy implementation
void* memcpy(void* dest, const void* src, size_t n) {
    uint8_t* d = (uint8_t*)dest;
    const uint8_t* s = (const uint8_t*)src;
    for (size_t i = 0; i < n; i++) {
        d[i] = s[i];
    }
    return dest;
}

// Option purchase input structure (must match Rust encoding)
typedef struct {
    uint8_t option_id[6];       // Option ID hash
    uint8_t buyer_pubkey[33];   // Bitcoin public key
    uint64_t quantity;          // Purchase quantity (satoshis)
    uint64_t premium;           // Premium amount (satoshis)
    uint64_t strike_price;      // Strike price (USD cents)
    uint64_t expiry;            // Expiry timestamp
    uint8_t option_type;        // 0=Call, 1=Put
    uint64_t current_spot;      // Current spot price (USD cents)
    uint64_t pool_balance;      // Pool balance (satoshis)
} PurchaseInput;

// Option purchase output structure
typedef struct {
    uint8_t purchase_id[8];     // Unique purchase ID
    uint8_t validation_hash[32]; // Validation hash
    uint64_t max_payout;        // Maximum payout (satoshis)
} PurchaseOutput;

// Simple hash function for validation
void hash_data(const uint8_t* data, size_t len, uint8_t* out) {
    // Simplified hash - in production use proper SHA256
    uint32_t hash = 0x811c9dc5; // FNV-1a initial value
    for (size_t i = 0; i < len; i++) {
        hash ^= data[i];
        hash *= 0x01000193; // FNV-1a prime
    }
    
    // Fill output with hash
    for (int i = 0; i < 32; i++) {
        out[i] = (hash >> ((i % 4) * 8)) & 0xFF;
        if ((i % 4) == 3) {
            hash = hash * 0x01000193 + i; // Mix for next bytes
        }
    }
}

// Generate purchase ID from inputs
void generate_purchase_id(const PurchaseInput* input, uint8_t* purchase_id) {
    // Combine option_id + buyer_pubkey first 2 bytes + timestamp
    purchase_id[0] = input->option_id[0];
    purchase_id[1] = input->option_id[1];
    purchase_id[2] = input->buyer_pubkey[0];
    purchase_id[3] = input->buyer_pubkey[1];
    purchase_id[4] = (input->expiry >> 24) & 0xFF;
    purchase_id[5] = (input->expiry >> 16) & 0xFF;
    purchase_id[6] = (input->expiry >> 8) & 0xFF;
    purchase_id[7] = input->expiry & 0xFF;
}

// Main validation function
void validate_purchase(const uint8_t* input_data, uint32_t input_len, 
                      uint8_t* output_data, uint32_t* output_len) {
    // Verify input length
    if (input_len != sizeof(PurchaseInput)) {
        *output_len = 0;
        return;
    }
    
    // Parse input
    PurchaseInput input;
    memcpy(&input, input_data, sizeof(PurchaseInput));
    
    // Validate basic constraints
    if (input.quantity == 0 || input.premium == 0) {
        *output_len = 0;
        return;
    }
    
    // Validate option type
    if (input.option_type > 1) {
        *output_len = 0;
        return;
    }
    
    // Validate premium is reasonable (not more than 50% of notional)
    uint64_t max_premium = input.quantity / 2;
    if (input.premium > max_premium) {
        *output_len = 0;
        return;
    }
    
    // Calculate maximum payout
    uint64_t max_payout;
    if (input.option_type == 0) { // Call
        max_payout = input.quantity; // Unlimited upside capped at notional
    } else { // Put
        // Max payout for put = strike * quantity / current_spot
        // Use 32-bit division to avoid __udivdi3
        if (input.current_spot > 0) {
            // Split into smaller operations to avoid 64-bit division
            uint32_t strike_low = input.strike_price & 0xFFFFFFFF;
            uint32_t quantity_low = input.quantity & 0xFFFFFFFF;
            uint32_t spot_low = input.current_spot & 0xFFFFFFFF;
            
            // Simplified calculation for 32-bit
            if (spot_low > 0) {
                max_payout = (strike_low * quantity_low) / spot_low;
            } else {
                max_payout = input.quantity;
            }
        } else {
            *output_len = 0;
            return;
        }
    }
    
    // Verify pool has sufficient balance
    if (input.pool_balance < max_payout) {
        *output_len = 0;
        return;
    }
    
    // Generate output
    PurchaseOutput output;
    
    // Generate purchase ID
    generate_purchase_id(&input, output.purchase_id);
    
    // Generate validation hash
    hash_data(input_data, input_len, output.validation_hash);
    
    // Set max payout
    output.max_payout = max_payout;
    
    // Copy output
    memcpy(output_data, &output, sizeof(PurchaseOutput));
    *output_len = sizeof(PurchaseOutput);
}

// Entry point for BitVMX
int main() {
    // BitVMX will provide input/output through specific memory locations
    // For now, just ensure the program compiles
    return 0;
}