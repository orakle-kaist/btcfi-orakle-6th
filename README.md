# BTCFi Oracle VM - Multi-Exchange Price Aggregation System

> **BTCFi Oracle VM**: BTC Layer 1 Native DeFi with multi-exchange price feeds and gRPC aggregation

## 🎯 Overview

BTCFi Oracle VM enables automated DeFi primitives directly on Bitcoin Layer 1 through:

- **Multi-Exchange Oracle Network**: Real-time price collection from Binance, Coinbase, Kraken
- **gRPC Price Aggregation**: Fault-tolerant consensus with average-based pricing
- **Synchronized Collection**: Time-aligned data gathering every minute at XX:00 seconds
- **K-line Data Integration**: 1-minute candlestick data from all supported exchanges

## 🏗️ Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│Oracle Node 1│    │Oracle Node 2│    │Oracle Node 3│
│  (Binance)  │    │ (Coinbase)  │    │  (Kraken)   │
└──────┬──────┘    └──────┬──────┘    └──────┬──────┘
       │                  │                  │
       └──────────────────┼──────────────────┘
                          │
                    ┌─────▼─────┐
                    │Aggregator │
                    │ (gRPC)    │
                    └─────┬─────┘
                          │
                    ┌─────▼─────┐
                    │Committer  │
                    │(Bitcoin L1│
                    └───────────┘
```

## 🚀 Quick Start

### 1. Start the Aggregator
```bash
cargo run -p aggregator
```

### 2. Start Oracle Nodes

**Option A: Automatic Multi-Node Setup**
```bash
# Start all 3 nodes automatically
./scripts/run_multi_nodes.sh

# Stop all nodes
./scripts/stop_nodes.sh
```

**Option B: Manual Node Setup**
```bash
# Terminal 1: Binance Node
cargo run -p oracle-node -- --exchange binance --node-id binance-node

# Terminal 2: Coinbase Node  
cargo run -p oracle-node -- --exchange coinbase --node-id coinbase-node

# Terminal 3: Kraken Node
cargo run -p oracle-node -- --exchange kraken --node-id kraken-node
```

### 3. Monitor System Status
```bash
# Check aggregator health and prices
python3 scripts/test_aggregator.py

# Monitor real-time logs
tail -f logs/node1_binance.log
tail -f logs/node2_coinbase.log
tail -f logs/node3_kraken.log
```

## 🔧 Configuration

### Oracle Node CLI Options
```bash
oracle-node [OPTIONS]

Options:
  --exchange <EXCHANGE>        Exchange to use: binance, coinbase, kraken [default: binance]
  --node-id <NODE_ID>         Unique node identifier
  --aggregator-url <URL>      gRPC Aggregator address [default: http://localhost:50051]
  --interval <SECONDS>        Collection interval in seconds [default: 60]
  --config <CONFIG>           Configuration file path [default: config/oracle-node.toml]
```

### Exchange APIs Used
- **Binance**: `/api/v3/klines` (1m interval K-line)
- **Coinbase**: `/products/BTC-USD/candles` (60s granularity)  
- **Kraken**: `/0/public/OHLC` (1m interval OHLC)

## 📊 System Features

### Price Collection
- **Synchronized Timing**: All nodes collect at exactly XX:00 seconds every minute
- **K-line Data**: Close price from 1-minute candlestick data across all exchanges
- **Fault Tolerance**: Exponential backoff retry on API failures
- **Price Validation**: Sanity checks for reasonable BTC price ranges

### Aggregation Logic
- **Average Calculation**: Simple mean of latest prices from each exchange
- **Deduplication**: One price per exchange (latest within 1-minute window)
- **Real-time Updates**: Immediate recalculation when new data arrives
- **Active Node Tracking**: Health monitoring with 2-minute timeout

### gRPC Services
```protobuf
service OracleService {
  rpc SubmitPrice(PriceRequest) returns (PriceResponse);
  rpc HealthCheck(HealthRequest) returns (HealthResponse);
  rpc GetAggregatedPrice(GetPriceRequest) returns (GetPriceResponse);
}
```

## 🛠️ Development

### Build
```bash
# Build all components
cargo build

# Build specific component
cargo build -p oracle-node
cargo build -p aggregator
```

### Testing
```bash
# Test individual exchanges
./scripts/test_exchanges.sh

# Run unit tests
cargo test

# Test with real APIs (network required)
cargo test --ignored
```

### Linting & Formatting
```bash
# Format code
cargo fmt

# Lint code
cargo clippy

# Generate documentation
cargo doc --open
```

## 🐛 Troubleshooting

### Common Issues

**1. "Cannot connect to gRPC Aggregator"**
```
❌ Cannot connect to gRPC Aggregator
💡 Make sure to run: cargo run -p aggregator
```

**2. "Rate limit exceeded"**
```
❌ Rate limit exceeded - Too many requests
💡 Wait a moment, automatic retry with exponential backoff
```

**3. "Multiple nodes for same exchange"**
```
📊 Calculated average from 6 nodes: $106,160.42
💡 Stop duplicate nodes: ./scripts/stop_nodes.sh
```

**4. "Failed to parse JSON response"**
```
❌ Failed to parse Kraken JSON response
💡 Check network connection and API availability
```

### Debug Commands
```bash
# Check running oracle processes
ps aux | grep oracle-node

# Kill specific processes
kill <PID1> <PID2> <PID3>

# Check aggregator logs
cargo run -p aggregator

# Verify individual exchange APIs
curl "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&limit=1"
```

## 📁 Project Structure

```
oracle_vm/
├── crates/
│   ├── oracle-node/          # Multi-exchange price collection
│   ├── aggregator/            # gRPC price aggregation service
│   └── common/                # Shared types and utilities
├── scripts/
│   ├── run_multi_nodes.sh     # Automated multi-node startup
│   ├── stop_nodes.sh          # Stop all oracle nodes
│   ├── test_exchanges.sh      # Individual exchange testing
│   └── test_aggregator.py     # gRPC aggregator testing
├── config/
│   ├── oracle-node-1.toml     # Binance node config
│   ├── oracle-node-2.toml     # Coinbase node config
│   └── oracle-node-3.toml     # Kraken node config
├── logs/                      # Runtime log files
└── proto/                     # Protocol Buffer definitions
```

## 🔮 Roadmap

- [x] Multi-exchange Oracle Node implementation
- [x] gRPC-based price aggregation
- [x] Synchronized 1-minute collection
- [x] K-line API integration (Binance, Coinbase, Kraken)
- [x] Automated multi-node management
- [ ] Bitcoin L1 anchoring via Taproot
- [ ] BitVMX proof generation integration
- [ ] DeFi primitives (vaults, options, RWA)
- [ ] Mainnet deployment readiness

## 📊 Current Status

**Phase 1: Oracle Layer** ✅ **COMPLETED**
- Multi-exchange price collection
- Real-time gRPC aggregation
- Fault-tolerant retry mechanisms
- Comprehensive monitoring and logging

**Next Phase: Bitcoin L1 Integration** 🚧 **IN PROGRESS**

## 📄 License

MIT License - see [LICENSE](LICENSE) for details

---

**🤖 Generated with [Claude Code](https://claude.ai/code)**