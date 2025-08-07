# BTCFi Contracts for BitVMX Protocol 2

This directory contains the complete option product registration system integrated with BitVMX verification protocol.

## Features

### Core Components

1. **BitVMX Option Registry** (`bitvmx_option_registry.rs`)
   - Option registration with BitVMX proof generation
   - Pre-signed transaction graphs for dispute resolution
   - Integration with Bitcoin network

2. **BitVMX Integration** (`bitvmx_integration.rs`)
   - Core BitVMX protocol integration
   - RISC-V program execution
   - Hash chain generation

3. **Proof Generator** (`bitvmx_proof_generator.rs`)
   - Settlement proof generation
   - Bitcoin script creation
   - Verification logic

4. **Emulator Integration** (`bitvmx_emulator_integration.rs`)
   - Direct BitVMX-CPU emulator integration
   - Option settlement calculation
   - Execution trace generation

5. **Simple Contract** (`simple_contract.rs`)
   - Basic option contract management
   - State management
   - Settlement processing

## Option Registration Process

1. **Input Validation**: Strike price, quantity, premium, expiry validation
2. **BitVMX Execution**: RISC-V program execution with verification
3. **Proof Generation**: Creation of cryptographic proofs
4. **Blockchain Anchoring**: Transaction creation and broadcast
5. **Settlement Ready**: Pre-signed settlement transactions

## RISC-V Programs

### Option Registration (`btcfi_option_registration.c`)
- Validates option parameters
- Generates unique option IDs
- Calculates collateral requirements
- Risk assessment

### Option Registration Realistic (`btcfi_option_registration_realistic.c`)
- Enhanced validation with Oracle price integration
- Realistic strike price ranges (10%-500% of current BTC price)
- Dynamic premium validation
- Risk level calculation

## Examples

### Basic Example
```bash
cargo run --example option_product_registration_with_proof
```

### Complete Flow
```bash
cargo run --example complete_option_registration_flow
```

### BitVMX Proof Generation
```bash
cargo run --example option_registration_bitvmx_proof
```

## Integration with BitVMX-CPU

The contracts integrate directly with the BitVMX-CPU emulator:

1. **RISC-V Execution**: Real execution of option logic
2. **Trace Generation**: Complete execution traces
3. **Proof Creation**: Cryptographic proofs of correct execution
4. **Challenge Protocol**: Dispute resolution mechanisms

## Option Product Structure

```rust
pub struct CompleteOptionProduct {
    pub product_id: String,
    pub option_type: OptionType,        // Call/Put
    pub strike_price: u64,              // USD cents
    pub quantity: u64,                  // satoshis
    pub premium: u64,                   // satoshis
    pub expiry_timestamp: u64,          // Unix timestamp
    pub issuer: String,                 // Issuer address
    pub current_btc_price: u64,         // Oracle BTC price
    pub oracle_sources: Vec<String>,    // Oracle sources
    pub bitvmx_proof_hash: [u8; 32],   // BitVMX proof
    pub registration_txid: Option<String>, // Bitcoin txid
    pub status: OptionStatus,           // Active/Settled/Expired
}
```

## Development

### Building
```bash
cargo build
```

### Testing
```bash
cargo test
```

### Running Examples
```bash
# Complete registration flow
cargo run --example complete_option_registration_flow

# Basic registration
cargo run --example option_product_registration_with_proof
```

## Requirements

- Rust 1.70+
- BitVMX-CPU emulator
- Bitcoin Core (for regtest)
- RISC-V toolchain (for program compilation)

## BitVMX Protocol 2 Improvements

This implementation includes several improvements over the original:

1. **Enhanced Validation**: More realistic option parameter validation
2. **Oracle Integration**: Real-time BTC price integration
3. **Risk Assessment**: Automated risk level calculation
4. **Complete Lifecycle**: From registration to settlement
5. **Production Ready**: Realistic constraints and validation

## License

Licensed under the same terms as the parent project.