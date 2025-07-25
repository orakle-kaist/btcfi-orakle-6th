# OP_RETURN Anchoring Documentation

## Overview

This document describes the Bitcoin OP_RETURN anchoring implementation for the BTCFi Oracle VM project. The anchoring system allows option registration data to be permanently recorded on the Bitcoin blockchain.

## OP_RETURN Data Schema

The system uses a compact schema to fit within Bitcoin's 80-byte OP_RETURN limit:

```
CREATE:{type}:{strike}:{expiry}
```

- `CREATE`: Protocol identifier (6 bytes)
- `type`: Option type - 0 for Call, 1 for Put (1 byte)
- `strike`: Strike price in USD cents (variable)
- `expiry`: Expiry timestamp or block height (variable)

### Example Data

```
Call option: CREATE:0:5000000:1735689600
Put option:  CREATE:1:4800000:1736294400
```

## Implementation

### Key Components

1. **OptionAnchorData** (`bitcoin_anchoring.rs`)
   - Encodes/decodes option data for OP_RETURN
   - Validates data size constraints

2. **BitcoinAnchoringService** (`bitcoin_anchoring.rs`)
   - Handles Bitcoin RPC communication
   - Creates and broadcasts OP_RETURN transactions
   - Verifies anchored data

3. **SimpleContractManager** (`simple_contract.rs`)
   - Extended with `create_option_with_anchor()` method
   - Combines option creation with on-chain anchoring

### Usage Example

```rust
// Initialize services
let mut manager = SimpleContractManager::new();
let anchoring = BitcoinAnchoringService::regtest();

// Create option with anchoring
let txid = manager.create_option_with_anchor(
    "CALL_001".to_string(),
    OptionType::Call,
    50000_00,    // $50,000 strike
    10_000_000,  // 0.1 BTC
    500_000,     // 0.005 BTC premium
    144 * 7,     // 1 week expiry
    "user123".to_string(),
    &anchoring,
).await?;
```

## Testing

### Prerequisites

1. Install Bitcoin Core
2. Start regtest node:
   ```bash
   bitcoind -regtest -daemon \
     -rpcuser=test -rpcpassword=test \
     -rpcallowip=127.0.0.1 \
     -fallbackfee=0.00001
   ```

3. Create wallet:
   ```bash
   bitcoin-cli -regtest createwallet "test"
   bitcoin-cli -regtest -generate 101
   ```

### Running Tests

```bash
# Unit tests
cargo test --package contracts test_anchor_data_schema

# Integration test
cargo test --package contracts test_option_anchoring_on_regtest -- --ignored

# Full demo
cargo run --example option_anchoring_demo
```

### Automated Test Script

```bash
./scripts/test_bitcoin_anchoring.sh
```

## Verification

To verify OP_RETURN data in a transaction:

```bash
# Get raw transaction
bitcoin-cli -regtest getrawtransaction <txid> true

# Extract OP_RETURN data
bitcoin-cli -regtest getrawtransaction <txid> true | \
  jq '.vout[] | select(.scriptPubKey.type == "nulldata")'
```

## Integration with BitVMX

The anchored option data serves as an immutable record that can be referenced during BitVMX settlement:

1. Option creation → OP_RETURN anchor
2. At expiry → BitVMX reads anchor data
3. Settlement uses anchored strike price
4. Disputes reference on-chain proof

## Cost Optimization

Future enhancements from Price Anchoring Branch:

1. **Batch Anchoring**: Multiple options in one transaction
2. **Tiered Service**: Instant vs delayed anchoring
3. **Compression**: Optimize data encoding

## Security Considerations

- OP_RETURN data is public and permanent
- No sensitive information should be anchored
- Option IDs should be hashed if privacy needed
- Anchoring txid serves as proof of registration time