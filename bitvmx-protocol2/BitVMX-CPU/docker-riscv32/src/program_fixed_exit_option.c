// BTCFi Buyer-Only Option Product Registration
// 단방향 옵션 상품 등록 전용 (구매/정산은 별도 pre-sign으로 처리)

typedef unsigned int uint32_t;

// MMIO addresses for BitVMX
#define INPUT_ADDR   ((volatile uint32_t*)0xAA000000)  
#define OUTPUT_ADDR  ((volatile uint32_t*)0xAB000000)  

// Input buffer section for BitVMX
__attribute__((section(".input")))
volatile uint32_t input_buffer[16];

// Output buffer section for BitVMX  
__attribute__((section(".output")))
volatile uint32_t output_buffer[16];

// Simple entry point - minimal setup like program_fixed_exit
__asm__(
    ".section .text.entry\n"
    ".global _start\n"
    "_start:\n"
    "  li sp, 0xE0001000\n"    // Stack at 0xE0001000 like original
    "  call main\n"
    "  li a0, 0\n"
    "  li s1, 0x5d0\n"          // Fixed exit pattern from original
    "  ebreak\n"
);

int main(void) {
    // 단방향 옵션 상품 등록 입력
    // [option_type, strike_price, expiry_timestamp, pool_size]
    uint32_t option_type = INPUT_ADDR[0];   // 0=Call, 1=Put
    uint32_t strike = INPUT_ADDR[1];        // 행사가 (USD)
    uint32_t expiry = INPUT_ADDR[2];        // 만기 timestamp
    uint32_t pool_size = INPUT_ADDR[3];     // 풀 사이즈 (sats)
    
    // 등록 검증
    uint32_t registered = 1;
    uint32_t error_code = 0;
    uint32_t product_id = 0;
    uint32_t required_liquidity = 0;
    
    // Option type check (0=Call, 1=Put)
    if (option_type > 1) {
        registered = 0;
        error_code = 1; // Invalid option type
    }
    
    // Strike price range check (1K ~ 500K USD)
    if (registered && (strike < 1000 || strike > 500000)) {
        registered = 0;
        error_code = 2; // Strike out of range
    }
    
    // Expiry check (최소 1시간 ~ 최대 90일)
    uint32_t current_time = 1735689600; // 2025-01-01 placeholder
    uint32_t min_expiry = current_time + 3600;      // +1 hour
    uint32_t max_expiry = current_time + 7776000;   // +90 days
    
    if (registered && (expiry < min_expiry || expiry > max_expiry)) {
        registered = 0;
        error_code = 3; // Invalid expiry
    }
    
    // Pool size check (최소 0.1 BTC ~ 최대 100 BTC)
    if (registered && (pool_size < 10000000 || pool_size > 10000000000)) {
        registered = 0;
        error_code = 4; // Invalid pool size
    }
    
    // 상품 등록 성공 시
    if (registered) {
        // Generate product ID (simple hash)
        product_id = (option_type * 1000000) + (strike % 1000000);
        
        // Calculate required liquidity for the pool
        // 단방향 옵션이므로 풀이 모든 리스크 부담
        if (option_type == 0) {
            // Call: 풀은 BTC 보유 필요
            required_liquidity = pool_size;
        } else {
            // Put: 풀은 USD 상당 BTC 보유 필요 (simplified)
            required_liquidity = (strike * pool_size) / 50000; // Assume $50K/BTC
        }
    }
    
    // Write output
    OUTPUT_ADDR[0] = registered;        // 1=등록성공, 0=실패
    OUTPUT_ADDR[1] = error_code;        // 에러 코드
    OUTPUT_ADDR[2] = product_id;        // 상품 ID
    OUTPUT_ADDR[3] = required_liquidity;// 필요 유동성
    OUTPUT_ADDR[4] = option_type;       // Echo back
    OUTPUT_ADDR[5] = strike;            // Echo back
    OUTPUT_ADDR[6] = expiry;            // Echo back
    OUTPUT_ADDR[7] = 0x4254;            // "BT" signature
    
    return 0;
}