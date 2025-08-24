// BTCFi Option Registration for BitVMX - Version 3 (Optimized/Safe)

// ===== 0) Stack in .bss (same idea, symbol resolved by linker) =====
__attribute__((used, aligned(16), section(".bss")))
static unsigned char __stack_area[128 * 1024];
asm(".globl __stack_top\n"
    ".equ __stack_top, __stack_area + (128 * 1024)\n");

__asm__(
    ".section .text.entry\n"
    ".global _start\n"
    "_start:\n"
    "    la sp, __stack_top\n"
    "    call main\n"
    "_hang:\n"
    "    j _hang\n"
);

// ===== 1) IO base (volatile) =====
#define INPUT_ADDRESS  ((volatile uint8_t*)0xAA000000)
#define OUTPUT_ADDRESS ((volatile uint8_t*)0xAA001000)

typedef unsigned char      uint8_t;
typedef unsigned short     uint16_t;
typedef unsigned int       uint32_t;
typedef unsigned long long uint64_t;
typedef long long          int64_t;

// ===== 2) tiny libc =====
static void* memset(void* s, int c, unsigned long n) {
    uint8_t* p = (uint8_t*)s;
    for (unsigned long i = 0; i < n; i++) p[i] = (uint8_t)c;
    return s;
}

// ===== 3) cheap 64-bit div (rv32) =====
static uint64_t udiv64(uint64_t dividend, uint64_t divisor) {
    if (!divisor || dividend < divisor) return (divisor==0)?0:0;
    uint64_t q=0, r=0;
    for (int i = 63; i >= 0; --i) {
        r = (r<<1) | ((dividend>>i)&1);
        if (r >= divisor) { r -= divisor; q |= (1ULL<<i); }
    }
    return q;
}

// ===== 4) domain structs (padding kept minimal; RV32 친화) =====
typedef struct {
    uint64_t total_liquidity;
    uint64_t available_liquidity;
    int64_t  net_delta;
    uint64_t total_premium_collected;
    uint32_t max_delta_ratio_bps;
} BTCFiPoolState;

typedef struct {
    uint32_t option_type;           // 0=Call, 1=Put
    uint32_t _pad1;
    uint64_t strike_price;          // cents/BTC
    uint64_t expiry_timestamp;
    uint64_t current_timestamp;
    uint64_t max_size;              // sats
    uint64_t current_spot_price;    // cents/BTC
    uint64_t base_premium_rate;     // bps
    int64_t  option_delta_per_btc;  // delta per 1 BTC (scaled 1e8 if 필요)
    uint64_t implied_volatility;    // bps
    BTCFiPoolState pool_state;
    uint32_t oracle_count;
    uint32_t _pad2;
    uint64_t oracle_timestamps[3];
    uint64_t oracle_prices[3];
} BTCFiOptionInput;

typedef struct {
    uint32_t validation_result;     // 1 ok
    uint32_t rejection_reason;
    uint64_t accepted_size;         // sats
    uint64_t required_collateral;   // sats
    uint64_t premium_amount;        // sats
    int64_t  new_pool_delta;
    uint32_t delta_ratio_after_bps;
    uint32_t risk_level;
    uint64_t effective_timestamp;
} BTCFiOptionOutput;

// ===== 5) policy =====
#define MIN_STRIKE_PRICE        100000ULL          // $1
#define MAX_STRIKE_PRICE  50000000000ULL          // $500k
#define MIN_QUANTITY           10000ULL           // 0.0001 BTC
#define MAX_QUANTITY    10000000000ULL            // 100 BTC
#define MIN_PREMIUM_BPS           10U             // 0.1%
#define MAX_ORACLE_AGE          300ULL            // 5 min
#define MAX_PRICE_DEV_BPS       200ULL            // 2%
#define MIN_EXPIRY_TIME        3600ULL            // 1h
#define MAX_EXPIRY_TIME    31536000ULL            // 1y
#define CONSERVATIVE_FACTOR       80U             // 80%

// === 추가: 안전 클램프(오버플로 방지/현실구간 가정) ===
#define MAX_RATIO_BPS     1000000ULL  // 10000% (x100) 상한
#define MIN_FLOOR_CENTS     10000ULL  // $100 최소 바닥(현실성/안전성 겸)
#define ONE_BTC_SATS   100000000ULL

// ===== 6) utils =====
static inline uint64_t uabs64(int64_t x){ return (x<0)?(uint64_t)(-x):(uint64_t)x; }
static inline uint64_t umin64(uint64_t a, uint64_t b){ return (a<b)?a:b; }
static inline uint64_t umin3(uint64_t a, uint64_t b, uint64_t c){
    uint64_t m = (a<b)?a:b; return (m<c)?m:c;
}

// (오라클 검증) 3개 고정 → 분기 언롤로 루프 비용 제거
static uint32_t validate_oracles_fast(const BTCFiOptionInput* in) {
    if (in->oracle_count != 3) return 7; // REJECT_STALE_ORACLE

    uint64_t now = in->current_timestamp;
    uint64_t t0 = in->oracle_timestamps[0];
    uint64_t t1 = in->oracle_timestamps[1];
    uint64_t t2 = in->oracle_timestamps[2];
    if (now - t0 > MAX_ORACLE_AGE) return 7;
    if (now - t1 > MAX_ORACLE_AGE) return 7;
    if (now - t2 > MAX_ORACLE_AGE) return 7;

    // dev check
    uint64_t p0 = in->oracle_prices[0];
    uint64_t p1 = in->oracle_prices[1];
    uint64_t p2 = in->oracle_prices[2];
    uint64_t avg = (p0 + p1 + p2) / 3ULL;
    if (avg == 0) return 8; // REJECT_ORACLE_DEVIATION

    uint64_t d0 = uabs64((int64_t)p0 - (int64_t)avg);
    uint64_t d1 = uabs64((int64_t)p1 - (int64_t)avg);
    uint64_t d2 = uabs64((int64_t)p2 - (int64_t)avg);
    if (udiv64(d0*10000ULL, avg) > MAX_PRICE_DEV_BPS) return 8;
    if (udiv64(d1*10000ULL, avg) > MAX_PRICE_DEV_BPS) return 8;
    if (udiv64(d2*10000ULL, avg) > MAX_PRICE_DEV_BPS) return 8;

    return 0;
}

// 바닥가(센트) 단순/보수 추정
static uint64_t floor_price_cents(uint64_t spot, uint64_t iv_bps, uint64_t tte) {
    if (spot == 0) return MIN_FLOOR_CENTS; // 방어
    uint64_t floor = udiv64(spot * CONSERVATIVE_FACTOR, 100ULL); // 80%
    if (iv_bps > 5000) floor = udiv64(floor * 90ULL, 100ULL);    // -10%
    if (tte > 30ULL*24ULL*3600ULL) floor = udiv64(floor * 95ULL, 100ULL); // -5%
    if (floor < MIN_FLOOR_CENTS) floor = MIN_FLOOR_CENTS;        // 절대 최저
    return floor;
}

// 프리미엄(bps/리스크 가중) - 나눗셈 최소화
static uint64_t calc_premium_sats(const BTCFiOptionInput* in, uint64_t size_sats, int64_t new_delta) {
    if (size_sats == 0) return 0;

    // base
    uint64_t prem = udiv64(size_sats * in->base_premium_rate, 10000ULL);

    // delta 리스크 가중: (|Δ|/Liquidity)*size, bps를 한 번만 사용
    if (in->pool_state.total_liquidity > 0) {
        uint64_t delta_bps = udiv64(uabs64(new_delta) * 10000ULL, in->pool_state.total_liquidity);
        prem += udiv64(size_sats * delta_bps, 100000ULL); // = size * (delta_bps/1e4) * 0.01
    }

    // 만기 7d↑ 가중
    uint64_t tte = in->expiry_timestamp - in->current_timestamp;
    if (tte > 7ULL*24ULL*3600ULL) prem = udiv64(prem * 110ULL, 100ULL);

    // 고 IV 가중
    if (in->implied_volatility > 5000ULL) prem = udiv64(prem * 120ULL, 100ULL);

    // 최소 프리미엄
    uint64_t min_prem = udiv64(size_sats * MIN_PREMIUM_BPS, 10000ULL);
    return (prem < min_prem) ? min_prem : prem;
}

// ===== 7) 메인 =====
int main(int argc) {
    // 입력 MMIO → 로컬 스택 구조체 (정렬/미정렬 안전)
    BTCFiOptionInput in;
    {
        volatile const uint8_t* ip = INPUT_ADDRESS;
        uint8_t* dp = (uint8_t*)&in;
        for (unsigned i=0; i<sizeof(BTCFiOptionInput); ++i) dp[i] = ip[i];
    }

    BTCFiOptionOutput out;
    memset(&out, 0, sizeof(out));

    // ---- Basic validation (조기탈락으로 스텝 절감) ----
    if (in.option_type > 1) { out.rejection_reason = 1; goto FINALIZE; } // INVALID_TYPE
    if (in.strike_price < MIN_STRIKE_PRICE || in.strike_price > MAX_STRIKE_PRICE) {
        out.rejection_reason = 2; goto FINALIZE;                           // INVALID_STRIKE
    }
    if (in.max_size < MIN_QUANTITY || in.max_size > MAX_QUANTITY) {
        out.rejection_reason = 3; goto FINALIZE;                           // INVALID_SIZE
    }
    uint64_t tte = (in.expiry_timestamp > in.current_timestamp)
                 ? (in.expiry_timestamp - in.current_timestamp) : 0ULL;
    if (tte < MIN_EXPIRY_TIME || tte > MAX_EXPIRY_TIME) {
        out.rejection_reason = 4; goto FINALIZE;                           // INVALID_EXPIRY
    }
    { // 오라클 검사(언롤)
        uint32_t rej = validate_oracles_fast(&in);
        if (rej) { out.rejection_reason = rej; goto FINALIZE; }
    }

    // ---- Liquidity cap ----
    uint64_t cap_liq;
    if (in.option_type == 0) {
        // CALL: 담보=BTC → 사용 가능 유동성
        cap_liq = in.pool_state.available_liquidity;
    } else {
        // PUT: 보수적 바닥가 기반 BTC 요구
        uint64_t floor_c = floor_price_cents(in.current_spot_price, in.implied_volatility, tte);
        // required = (strike/floor) * size, overflow-safe 근사:
        // ratio_bps = min( (strike*10000)/floor, MAX_RATIO_BPS )
        uint64_t ratio_bps = udiv64(in.strike_price * 10000ULL, floor_c);
        if (ratio_bps > MAX_RATIO_BPS) ratio_bps = MAX_RATIO_BPS;

        // cap_liq = available_BTC / ratio  →  available * 10000 / ratio_bps
        if (ratio_bps == 0) { out.rejection_reason = 5; goto FINALIZE; } // 방어
        cap_liq = udiv64(in.pool_state.available_liquidity * 10000ULL, ratio_bps);
    }

    // ---- Delta cap ----
    uint64_t cap_delta = MAX_QUANTITY;
    if (in.pool_state.total_liquidity > 0 && in.option_delta_per_btc != 0) {
        uint64_t max_allowed_delta = udiv64(in.pool_state.total_liquidity * in.pool_state.max_delta_ratio_bps, 10000ULL);
        int64_t cur = in.pool_state.net_delta;
        int64_t room = (int64_t)max_allowed_delta - (int64_t)uabs64(cur);
        if (room <= 0) {
            cap_delta = 0;
        } else {
            // size_sats = room / |delta per 1 BTC| (BTC 단위) → sats 로 변환
            // option_delta_per_btc 가 (delta per 1 BTC)라면:
            uint64_t d = (uint64_t)uabs64(in.option_delta_per_btc);
            // room/d = 허용 BTC 수, *1e8 = sats
            cap_delta = udiv64((uint64_t)room * ONE_BTC_SATS, d);
        }
    }

    // ---- 실제 수용 사이즈 ----
    out.accepted_size = umin3(in.max_size, cap_liq, cap_delta);
    if (out.accepted_size < MIN_QUANTITY) { out.rejection_reason = 5; goto FINALIZE; } // INSUFF_LIQ

    // ---- new delta / delta ratio ----
    {
        // delta_change = option_delta_per_btc * (accepted_size / 1 BTC)
        uint64_t size_btc_fp = udiv64(out.accepted_size, ONE_BTC_SATS); // 정수 BTC만 반영(스텝 절약)
        int64_t delta_change = (int64_t)( (int64_t)in.option_delta_per_btc * (int64_t)size_btc_fp );
        out.new_pool_delta = in.pool_state.net_delta + delta_change;

        if (in.pool_state.total_liquidity > 0) {
            out.delta_ratio_after_bps = udiv64(uabs64(out.new_pool_delta) * 10000ULL, in.pool_state.total_liquidity);
            if (out.delta_ratio_after_bps > in.pool_state.max_delta_ratio_bps) {
                out.rejection_reason = 6; out.accepted_size = 0; goto FINALIZE;
            }
        }
    }

    // ---- required collateral (정확·안전 계산) ----
    if (in.option_type == 0) {
        out.required_collateral = out.accepted_size; // CALL
    } else {
        uint64_t floor_c = floor_price_cents(in.current_spot_price, in.implied_volatility, tte);

        // BPS 비율 근사 사용 (더 안전하고 예측 가능)
        uint64_t ratio_bps = udiv64(in.strike_price * 10000ULL, floor_c);
        if (ratio_bps > MAX_RATIO_BPS) ratio_bps = MAX_RATIO_BPS;
        // req = size * ratio_bps / 10000
        out.required_collateral = udiv64(out.accepted_size * ratio_bps, 10000ULL);
    }

    // ---- premium ----
    out.premium_amount = calc_premium_sats(&in, out.accepted_size, out.new_pool_delta);

    // ---- risk ----
    out.risk_level = (out.delta_ratio_after_bps > 1500U) ? 3 :
                     (out.delta_ratio_after_bps > 1000U) ? 2 : 1;

    out.effective_timestamp = in.current_timestamp;
    out.validation_result = 1;  // APPROVED

FINALIZE:
    // MMIO store with volatile (방출 순서 보장)
    {
        volatile uint8_t* op = OUTPUT_ADDRESS;
        const uint8_t* sp = (const uint8_t*)&out;
        for (unsigned i=0; i<sizeof(BTCFiOptionOutput); ++i) op[i] = sp[i];
        __asm__ __volatile__("" ::: "memory");
    }
    return out.validation_result;
}