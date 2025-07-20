#!/bin/bash

# Test Bitcoin testnet connection
# This script checks if we can connect to a Bitcoin testnet node

echo "🔗 Testing Bitcoin testnet connection..."

# Test with curl
echo "📡 Testing Bitcoin RPC connection..."

# Default testnet RPC configuration
RPC_URL="http://localhost:18332"
RPC_USER="bitcoinrpc"
RPC_PASS="rpcpassword"

# Test getnetworkinfo
echo "Getting network info..."
curl -s -u "$RPC_USER:$RPC_PASS" \
     -d '{"jsonrpc":"1.0","id":"test","method":"getnetworkinfo","params":[]}' \
     -H 'Content-Type: application/json' \
     "$RPC_URL" | jq '.'

if [ $? -eq 0 ]; then
    echo "✅ Successfully connected to Bitcoin testnet node"
    
    # Get additional info
    echo "📊 Getting blockchain info..."
    curl -s -u "$RPC_USER:$RPC_PASS" \
         -d '{"jsonrpc":"1.0","id":"test","method":"getblockchaininfo","params":[]}' \
         -H 'Content-Type: application/json' \
         "$RPC_URL" | jq '.result | {chain, blocks, difficulty}'
    
    echo "💰 Getting wallet info..."
    curl -s -u "$RPC_USER:$RPC_PASS" \
         -d '{"jsonrpc":"1.0","id":"test","method":"getwalletinfo","params":[]}' \
         -H 'Content-Type: application/json' \
         "$RPC_URL" | jq '.result | {balance, txcount}'
         
else
    echo "❌ Failed to connect to Bitcoin testnet node"
    echo ""
    echo "💡 To set up Bitcoin testnet:"
    echo "1. Install Bitcoin Core"
    echo "2. Create bitcoin.conf with:"
    echo "   testnet=1"
    echo "   server=1"
    echo "   rpcuser=bitcoinrpc"
    echo "   rpcpassword=rpcpassword"
    echo "   rpcport=18332"
    echo "   rpcallowip=127.0.0.1"
    echo "3. Start bitcoind with: bitcoind -testnet"
    echo "4. Create wallet: bitcoin-cli -testnet createwallet \"testwallet\""
    echo ""
    echo "🪙 Get testnet coins from: https://coinfaucet.eu/en/btc-testnet/"
fi