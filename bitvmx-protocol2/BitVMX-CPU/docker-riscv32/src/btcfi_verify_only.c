// BTCFi Verification Only - Target: <30 steps
// All calculations done off-chain, only verify result

#define INPUT_ADDRESS ((unsigned int*)0xAA000000)
#define OUTPUT_ADDRESS ((unsigned int*)0xAA001000)

int main() {
    // Input structure (from off-chain calculation):
    // [0]: computed_payout (satoshis)
    // [1]: expected_hash (first 4 bytes)
    // [2]: actual_hash (first 4 bytes)
    
    unsigned int payout = INPUT_ADDRESS[0];
    unsigned int expected = INPUT_ADDRESS[1];
    unsigned int actual = INPUT_ADDRESS[2];
    
    // Simple verification: hash match
    if (expected == actual) {
        OUTPUT_ADDRESS[0] = payout;  // Valid: return payout
        OUTPUT_ADDRESS[1] = 1;        // Success flag
    } else {
        OUTPUT_ADDRESS[0] = 0;        // Invalid: no payout
        OUTPUT_ADDRESS[1] = 0;        // Failure flag
    }
    
    // Halt
    while(1);
}