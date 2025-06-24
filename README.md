# Oracle VM - Bitcoin Layer 1 DeFi System

> Oracle VM for BTC Layer 1 Anchoring Rollup implementing automated DeFi primitives

## Overview

Oracle VM is a Rust-based system that enables automated DeFi primitives on Bitcoin Layer 1 through:

- **External Oracle Layer**: Multi-source price data collection and aggregation
- **Bitcoin L1 Anchoring**: Price root storage via Taproot UTXO and OP_RETURN
- **BitVMX Integration**: Proof generation and verification for settlement automation

## Architecture

```
Oracle Nodes → Aggregator → Committer → Bitcoin L1
                    ↓
              BitVMX Oracle VM
                    ↓
            DeFi Primitives (Vaults, Options, RWA)
```

## Components

### Core Crates

- **`oracle-vm-common`**: Shared types, utilities, and cryptographic functions
- **`oracle-node`**: Price data collection from exchanges (Binance, Coinbase, etc.)
- **`aggregator`**: Multi-node consensus and price aggregation
- **`committer`**: Bitcoin L1 anchoring and transaction management
- **`bitcoin-client`**: Bitcoin RPC interface and script management
- **`bitvmx-integration`**: BitVMX proof system integration
- **`defi-primitives`**: Vault liquidation, option settlement, RWA modules

## Quick Start

### Prerequisites

- Rust 1.70+
- Bitcoin Core (for testing)

### Build

```bash
# Build all components
cargo build --release

# Build specific component
cargo build --bin oracle-node --release
```

### Run

```bash
# Oracle Node
cargo run --bin oracle-node -- --config config/oracle-node.toml

# Aggregator
cargo run --bin aggregator -- --config config/aggregator.toml

# Committer
cargo run --bin committer -- --config config/committer.toml
```

### Test

```bash
# Run all tests
cargo test

# Run tests for specific crate
cargo test -p oracle-vm-common
```

### Development

```bash
# Format code
cargo fmt

# Lint
cargo clippy

# Generate documentation
cargo doc --open
```

## Configuration

Each component uses TOML configuration files:

- `config/oracle-node.toml`: Oracle node settings
- `config/aggregator.toml`: Aggregator and consensus settings  
- `config/committer.toml`: Bitcoin client and anchoring settings

## Project Status

- [x] Project structure and common utilities
- [ ] Oracle node implementation
- [ ] Price aggregation and consensus
- [ ] Bitcoin L1 anchoring
- [ ] BitVMX integration
- [ ] DeFi primitive modules

## License

MIT License