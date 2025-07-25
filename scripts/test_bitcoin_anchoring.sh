#!/bin/bash
# Test Bitcoin OP_RETURN anchoring on regtest

set -e

echo "=== Bitcoin OP_RETURN Anchoring Test ==="
echo

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if bitcoind is installed
if ! command -v bitcoind &> /dev/null; then
    echo -e "${RED}Error: bitcoind not found. Please install Bitcoin Core.${NC}"
    exit 1
fi

# Check if bitcoin-cli is installed
if ! command -v bitcoin-cli &> /dev/null; then
    echo -e "${RED}Error: bitcoin-cli not found. Please install Bitcoin Core.${NC}"
    exit 1
fi

# Function to check if bitcoind is running
is_bitcoind_running() {
    bitcoin-cli -regtest -rpcuser=test -rpcpassword=test getblockcount &> /dev/null
}

# Start Bitcoin regtest if not running
if is_bitcoind_running; then
    echo -e "${GREEN}✓ Bitcoin regtest is already running${NC}"
else
    echo "Starting Bitcoin regtest node..."
    bitcoind -regtest -daemon \
        -rpcuser=test \
        -rpcpassword=test \
        -rpcallowip=127.0.0.1 \
        -rpcport=18443 \
        -fallbackfee=0.00001 \
        -txindex=1
    
    # Wait for startup
    sleep 3
    
    if is_bitcoind_running; then
        echo -e "${GREEN}✓ Bitcoin regtest started${NC}"
    else
        echo -e "${RED}Failed to start Bitcoin regtest${NC}"
        exit 1
    fi
fi

# Create or load wallet
echo
echo "Setting up wallet..."
if bitcoin-cli -regtest -rpcuser=test -rpcpassword=test listwallets | grep -q "test"; then
    echo -e "${GREEN}✓ Wallet 'test' already loaded${NC}"
else
    bitcoin-cli -regtest -rpcuser=test -rpcpassword=test createwallet "test" &> /dev/null || \
    bitcoin-cli -regtest -rpcuser=test -rpcpassword=test loadwallet "test" &> /dev/null
    echo -e "${GREEN}✓ Wallet 'test' created/loaded${NC}"
fi

# Check balance
BALANCE=$(bitcoin-cli -regtest -rpcuser=test -rpcpassword=test getbalance)
echo "Current balance: $BALANCE BTC"

# Generate blocks if balance is low
if (( $(echo "$BALANCE < 10" | bc -l) )); then
    echo "Generating blocks to get coins..."
    bitcoin-cli -regtest -rpcuser=test -rpcpassword=test -generate 101 > /dev/null
    BALANCE=$(bitcoin-cli -regtest -rpcuser=test -rpcpassword=test getbalance)
    echo -e "${GREEN}✓ Generated 101 blocks. New balance: $BALANCE BTC${NC}"
fi

# Run the Rust tests
echo
echo -e "${BLUE}Running OP_RETURN anchoring tests...${NC}"
echo

cd "$(dirname "$0")/.."

# Run unit tests
echo "1. Running unit tests..."
cargo test --package contracts --test bitcoin_anchoring_test test_anchor_data_schema -- --nocapture

# Run integration test (if regtest is ready)
echo
echo "2. Running integration test..."
cargo test --package contracts --test bitcoin_anchoring_test test_option_anchoring_on_regtest -- --ignored --nocapture

# Run demo
echo
echo "3. Running demo application..."
cargo run --example option_anchoring_demo

echo
echo -e "${GREEN}=== Test Complete ===${NC}"
echo
echo "To view OP_RETURN data in transactions:"
echo "bitcoin-cli -regtest getrawtransaction <txid> true | jq '.vout[] | select(.scriptPubKey.type == \"nulldata\")'"
echo
echo "To stop Bitcoin regtest:"
echo "bitcoin-cli -regtest stop"