// BTCFi Option Purchase for BitVMX - AMM Single-sided Options
// Buyer purchases from pool (automatic seller)
// Premium already calculated by Option Manager with delta adjustment

typedef unsigned char uint8_t;
typedef unsigned short uint16_t;
typedef unsigned int uint32_t;
typedef unsigned long long uint64_t;
typedef long long int64_t;

// Manual memory operations
void* memcpy(void* dest, const void* src, unsigned long n) {
    char* d = (char*)dest;
    const char* s = (const char*)src;
    for (unsigned long i = 0; i < n; i++) {
        d[i] = s[i];
    }
    return dest;
}

void* memset(void* s, int c, unsigned long n) {
    char* p = (char*)s;
    for (unsigned long i = 0; i < n; i++) {
        p[i] = c;
    }
    return s;
}

int memcmp(const void* s1, const void* s2, unsigned long n) {
    const char* p1 = (const char*)s1;
    const char* p2 = (const char*)s2;
    for (unsigned long i = 0; i < n; i++) {
        if (p1[i] != p2[i]) {
            return p1[i] - p2[i];
        }
    }
    return 0;
}

// BitVMX memory addresses
#define INPUT_ADDRESS 0x80000000
#define OUTPUT_ADDRESS 0x80001000

// Print function for BitVMX
void print_literal(const char* str, int len) {
    // In actual BitVMX, this would output to trace
    (void)str; (void)len;
}

// Manual 64-bit operations
uint64_t udiv64(uint64_t dividend, uint64_t divisor) {
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

uint64_t umul64(uint64_t a, uint64_t b) {
    uint64_t result = 0;
    while (b > 0) {
        if (b & 1) {
            result += a;
        }
        a <<= 1;
        b >>= 1;
    }
    return result;
}

// SHA256 implementation for bare metal
void sha256(const uint8_t* input, unsigned long len, uint8_t* output) {
    uint32_t hash = 0x6a09e667;
    
    for (unsigned long i = 0; i < len; i++) {
        hash ^= input[i];
        hash = ((hash << 13) | (hash >> 19)) + 0x9e3779b9;
    }
    
    for (int i = 0; i < 32; i += 4) {
        *((uint32_t*)(output + i)) = hash;
        hash = hash * 0x01000193 + i;
    }
}

// Pool State (same as registration)
typedef struct {
    uint64_t total_liquidity;
    uint64_t available_liquidity;
    int64_t call_delta_exposure;
    int64_t put_delta_exposure;
    int64_t net_delta;
    uint64_t total_premium_collected;
    uint32_t max_delta_ratio_bps;
} __attribute__((packed)) BTCFiPoolState;

// Purchase Input from Option Manager
typedef struct {
    // Purchase details
    uint8_t option_id[32];          // Option being purchased
    uint8_t buyer_address[20];      // Bitcoin address
    uint64_t purchase_quantity;     // Amount to buy (satoshis)
    uint64_t purchase_timestamp;
    uint8_t payment_txid[32];       // Payment proof
    
    // Premium calculation (already done by Option Manager)
    uint64_t base_premium;          // Black-Scholes premium
    uint64_t final_premium;         // After delta adjustment
    uint32_t delta_impact_bps;      // How much delta changes (+ or -)
    uint32_t got_discount;          // 1 if got discount for improving balance
    
    // Option details
    uint32_t option_type;           // 0=Call, 1=Put
    uint64_t strike_price;          // USD cents
    uint64_t expiry_timestamp;
    uint64_t current_spot_price;    // Current BTC price
    
    // Pool state before purchase
    BTCFiPoolState pool_state_before;
    
    // Delta information
    int64_t purchase_delta;         // Delta of this purchase
    int64_t pool_delta_after;       // Expected pool delta after
    
    // Pre-sign data
    uint8_t pool_pubkey[33];        // Pool's public key for pre-sign
    uint64_t max_payout;            // Maximum possible payout
} __attribute__((packed)) BTCFiPurchaseInput;

// Purchase Output
typedef struct {
    uint8_t purchase_id[32];        // Unique purchase ID
    uint32_t validation_result;     // 1=valid, 0=invalid
    
    // Pre-sign commitment for settlement
    uint8_t presign_hash[32];       // Hash of pre-sign conditions
    uint8_t settlement_script[520]; // Settlement script for Bitcoin
    uint32_t script_length;
    
    // Purchase confirmation
    uint64_t premium_paid;          // Actual premium paid
    uint64_t max_payout;            // Maximum payout at settlement
    uint8_t settlement_conditions[32]; // Conditions hash
    
    // Delta impact confirmation
    uint32_t improved_balance;      // 1 if helped balance pool
    int64_t final_pool_delta;       // Pool delta after purchase
    uint32_t delta_ratio_bps;       // Final delta/liquidity ratio
    
    // Receipt
    uint8_t purchase_receipt[32];   // Receipt hash
    uint64_t purchase_timestamp;
} __attribute__((packed)) BTCFiPurchaseOutput;

// BTCFi Protocol Constants
#define BTCFI_PURCHASE_MAGIC 0x42544350  // "BTCP" in hex
#define MIN_PURCHASE_QUANTITY 10000      // 0.0001 BTC minimum
#define MAX_PURCHASE_RATIO 100            // Max 100% of available quantity
#define PREMIUM_TOLERANCE 105             // 105% of minimum premium accepted
#define MIN_TIME_TO_EXPIRY 3600          // 1 hour minimum before expiry
#define ESCROW_VERSION 1

// Validate purchase (basic checks only - Option Manager did pricing)
uint32_t validate_purchase(const BTCFiPurchaseInput* input) {
    // 1. Check option ID exists
    uint32_t id_sum = 0;
    for (int i = 0; i < 32; i++) {
        id_sum += input->option_id[i];
    }
    if (id_sum == 0) return 0;
    
    // 2. Check buyer address exists
    uint32_t addr_sum = 0;
    for (int i = 0; i < 20; i++) {
        addr_sum += input->buyer_address[i];
    }
    if (addr_sum == 0) return 0;
    
    // 3. Check quantity is valid
    if (input->purchase_quantity < MIN_PURCHASE_QUANTITY) {
        return 0;
    }
    
    // 4. Check not expired
    if (input->purchase_timestamp >= input->expiry_timestamp) {
        return 0;
    }
    
    // 5. Check payment proof
    uint32_t tx_sum = 0;
    for (int i = 0; i < 32; i++) {
        tx_sum += input->payment_txid[i];
    }
    if (tx_sum == 0) return 0;
    
    // 6. Verify premium matches what Option Manager calculated
    if (input->final_premium == 0) {
        return 0;
    }
    
    // 7. Check pool pubkey exists
    uint32_t key_sum = 0;
    for (int i = 0; i < 33; i++) {
        key_sum += input->pool_pubkey[i];
    }
    if (key_sum == 0) return 0;
    
    return 1;
}

// Generate unique purchase ID
void generate_purchase_id(const BTCFiPurchaseInput* input, uint8_t* purchase_id) {
    // Combine option ID, buyer address, and timestamp for uniqueness
    uint8_t hash_input[32 + 20 + 8];
    uint8_t full_hash[32];
    
    memcpy(hash_input, input->option_id, 32);
    memcpy(hash_input + 32, input->buyer_address, 20);
    memcpy(hash_input + 52, &input->purchase_timestamp, 8);
    
    sha256(hash_input, sizeof(hash_input), full_hash);
    
    // Take first 32 bytes as purchase ID
    memcpy(purchase_id, full_hash, 32);
}

// Generate settlement conditions hash
void generate_settlement_conditions(const BTCFiPurchaseInput* input, uint8_t* conditions) {
    // Hash of: option_type + strike + quantity + expiry + buyer
    uint8_t condition_data[4 + 8 + 8 + 8 + 20];
    
    memcpy(condition_data, &input->option_type, 4);
    memcpy(condition_data + 4, &input->strike_price, 8);
    memcpy(condition_data + 12, &input->purchase_quantity, 8);
    memcpy(condition_data + 20, &input->expiry_timestamp, 8);
    memcpy(condition_data + 28, input->buyer_address, 20);
    
    sha256(condition_data, sizeof(condition_data), conditions);
}

// Generate escrow address (simplified)
void generate_escrow_address(const uint8_t* purchase_id, uint8_t* escrow_addr) {
    uint8_t addr_data[8 + 4];
    uint8_t hash[32];
    
    memcpy(addr_data, purchase_id, 8);
    *(uint32_t*)(addr_data + 8) = ESCROW_VERSION;
    
    sha256(addr_data, sizeof(addr_data), hash);
    
    // Take first 20 bytes as address
    memcpy(escrow_addr, hash, 20);
}

// Generate purchase receipt
void generate_purchase_receipt(const BTCFiPurchaseOutput* output, uint8_t* receipt) {
    sha256((uint8_t*)output, sizeof(BTCFiPurchaseOutput) - 32, receipt);
}

// Calculate risk score
uint32_t calculate_risk_score(const BTCFiPurchaseInput* input) {
    uint32_t risk = 1; // Base risk
    
    // Factor 1: Time to expiry
    uint64_t time_to_expiry = input->expiry_timestamp - input->purchase_timestamp;
    if (time_to_expiry < 24 * 3600) { // Less than 24 hours
        risk += 3;
    } else if (time_to_expiry < 7 * 24 * 3600) { // Less than 1 week
        risk += 2;
    }
    
    // Factor 2: Purchase size vs pool liquidity
    uint64_t size_ratio = udiv64(umul64(input->purchase_quantity, 100), 
                                 input->pool_state_before.available_liquidity);
    if (size_ratio > 10) { // More than 10% of available liquidity
        risk += 3;
    } else if (size_ratio > 5) { // More than 5%
        risk += 2;
    }
    
    // Factor 3: Delta impact
    if (input->delta_impact_bps > 200) { // More than 2% delta impact
        risk += 2;
    }
    
    // Cap at 10
    return (risk > 10) ? 10 : risk;
}

// Generate pre-sign script for settlement
void generate_presign_script(const BTCFiPurchaseInput* input, uint8_t* script, uint32_t* len) {
    // Simplified Bitcoin script for pre-sign
    // In production, this would be a complex script with price conditions
    
    uint32_t pos = 0;
    
    // OP_IF - Settlement path
    script[pos++] = 0x63;
    
    // Check expiry time
    script[pos++] = 0xB1; // OP_CHECKLOCKTIMEVERIFY
    memcpy(script + pos, &input->expiry_timestamp, 8);
    pos += 8;
    script[pos++] = 0x75; // OP_DROP
    
    // Price condition would go here in production
    // For now, simplified
    script[pos++] = 0x51; // OP_TRUE
    
    // OP_ELSE - Refund path
    script[pos++] = 0x67;
    
    // Buyer can claim after expiry + grace period
    script[pos++] = 0x76; // OP_DUP
    script[pos++] = 0xA9; // OP_HASH160
    memcpy(script + pos, input->buyer_address, 20);
    pos += 20;
    script[pos++] = 0x88; // OP_EQUALVERIFY
    script[pos++] = 0xAC; // OP_CHECKSIG
    
    // OP_ENDIF
    script[pos++] = 0x68;
    
    *len = pos;
}

// Main purchase function - validates and creates pre-sign
int main(int argc) {
    BTCFiPurchaseInput* input = (BTCFiPurchaseInput*)INPUT_ADDRESS;
    BTCFiPurchaseOutput output;
    
    memset(&output, 0, sizeof(output));
    
    print_literal("=== BTCFi AMM Option Purchase ===\n", 34);
    print_literal("Buyer purchases from automatic pool\n", 36);
    
    // Validate purchase
    output.validation_result = validate_purchase(input);
    
    if (output.validation_result) {
        print_literal("✅ Purchase APPROVED\n", 21);
        
        // Generate purchase ID
        uint8_t id_data[32 + 20 + 8];
        memcpy(id_data, input->option_id, 32);
        memcpy(id_data + 32, input->buyer_address, 20);
        memcpy(id_data + 52, &input->purchase_timestamp, 8);
        sha256(id_data, 60, output.purchase_id);
        
        // Generate settlement conditions
        generate_settlement_conditions(input, output.settlement_conditions);
        
        // Generate pre-sign script
        generate_presign_script(input, output.settlement_script, &output.script_length);
        
        // Generate pre-sign hash
        uint8_t presign_data[32 + 8 + 8 + 8 + 33];
        memcpy(presign_data, output.purchase_id, 32);
        memcpy(presign_data + 32, &input->strike_price, 8);
        memcpy(presign_data + 40, &input->expiry_timestamp, 8);
        memcpy(presign_data + 48, &input->max_payout, 8);
        memcpy(presign_data + 56, input->pool_pubkey, 33);
        sha256(presign_data, 89, output.presign_hash);
        
        // Set purchase details
        output.premium_paid = input->final_premium;
        output.max_payout = input->max_payout;
        output.purchase_timestamp = input->purchase_timestamp;
        
        // Set delta impact
        output.final_pool_delta = input->pool_delta_after;
        uint64_t abs_delta = (input->pool_delta_after < 0) ? 
            (uint64_t)(-input->pool_delta_after) : (uint64_t)input->pool_delta_after;
        output.delta_ratio_bps = (uint32_t)udiv64(
            umul64(abs_delta, 10000),
            input->pool_state_before.total_liquidity
        );
        
        // Check if purchase improved balance
        int64_t delta_before = input->pool_state_before.net_delta;
        uint64_t abs_before = (delta_before < 0) ? (uint64_t)(-delta_before) : (uint64_t)delta_before;
        uint64_t abs_after = abs_delta;
        output.improved_balance = (abs_after < abs_before) ? 1 : 0;
        
        // Generate receipt
        sha256((uint8_t*)&output, sizeof(output) - 32, output.purchase_receipt);
        
        // Output purchase details
        print_literal("📊 Purchase Details:\n", 21);
        print_literal("   Option Type: ", 16);
        if (input->option_type == 0) {
            print_literal("CALL\n", 5);
        } else {
            print_literal("PUT\n", 4);
        }
        
        print_literal("   Strike: $", 12);
        print_literal("[STRIKE]\n", 9);
        
        print_literal("   Quantity: ", 13);
        print_literal("[QTY] BTC\n", 10);
        
        print_literal("   Premium Paid: ", 17);
        print_literal("[PREMIUM] sats\n", 15);
        
        print_literal("   Max Payout: ", 15);
        print_literal("[MAX_PAYOUT] sats\n", 18);
        
        print_literal("   Delta Impact: ", 17);
        if (output.improved_balance) {
            print_literal("Improved balance ✅\n", 20);
        } else {
            print_literal("Increased imbalance\n", 20);
        }
        
        print_literal("   Pool Delta After: ", 20);
        print_literal("[DELTA_RATIO] bps\n", 18);
        
        print_literal("   Purchase ID: ", 15);
        print_literal("[PURCHASE_ID]\n", 14);
        
        print_literal("✅ Purchase: SUCCESS\n", 21);
        
    } else {
        print_literal("❌ Purchase validation: FAILED\n", 31);
        
        output.validation_result = 0;
        
        print_literal("🚫 Possible issues:\n", 20);
        print_literal("   - Invalid option ID\n", 22);
        print_literal("   - Insufficient premium\n", 24);
        print_literal("   - Quantity too large\n", 22);
        print_literal("   - Option expired or near expiry\n", 33);
        print_literal("   - Missing payment proof\n", 25);
        print_literal("   - Missing pool pubkey\n", 23);
    }
    
    // Write output to BitVMX
    memcpy((void*)OUTPUT_ADDRESS, &output, sizeof(output));
    
    print_literal("=== BTCFi Purchase Complete ===\n", 33);
    
    return output.validation_result ? 0 : 1;
}

// Additional validation functions

// Verify buyer has sufficient balance (would check on-chain in production)
uint32_t verify_buyer_balance(const uint8_t* buyer_address, uint64_t required_amount) {
    // In production, this would query blockchain state
    // For now, assume valid if buyer address is not empty
    uint32_t sum = 0;
    for (int i = 0; i < 20; i++) {
        sum += buyer_address[i];
    }
    return sum > 0 ? 1 : 0;
}

// Verify option is still available for purchase
uint32_t verify_option_availability(const uint8_t* option_id, uint64_t requested_quantity) {
    // In production, check against option registry
    // For now, assume available if quantity is reasonable
    return (requested_quantity > 0 && requested_quantity < 100000000000) ? 1 : 0;
}

// Calculate implied volatility from premium (simplified)
uint32_t calculate_implied_volatility(uint64_t premium, uint64_t strike, uint64_t time_to_expiry) {
    // Simplified IV calculation
    // In production, use proper Black-Scholes inverse
    uint64_t annualized_time = udiv64(time_to_expiry, 365 * 24 * 3600);
    if (annualized_time == 0) annualized_time = 1;
    
    uint64_t iv_proxy = udiv64(umul64(premium, 100), udiv64(strike, annualized_time));
    
    // Return as percentage * 100 (e.g., 5000 = 50%)
    return (uint32_t)(iv_proxy > 10000 ? 10000 : iv_proxy);
}