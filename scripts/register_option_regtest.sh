#!/bin/bash

# Register Option Product on Bitcoin Regtest
# Fast local testing version

set -e

echo "🚀 BTCFi Option Registration (Regtest)"
echo "====================================="

# Bitcoin regtest configuration
RPC_URL="http://localhost:18443"
RPC_USER="bitcoinrpc"
RPC_PASS="rpcpassword"

# Check Bitcoin connection
echo "🔗 Checking Bitcoin regtest connection..."
if ! curl -s -u "$RPC_USER:$RPC_PASS" \
     -d '{"jsonrpc":"1.0","id":"test","method":"getnetworkinfo","params":[]}' \
     -H 'Content-Type: application/json' \
     "$RPC_URL" > /dev/null; then
    echo "❌ Failed to connect to Bitcoin regtest"
    echo "💡 Run: ./scripts/bitcoin_start.sh regtest"
    exit 1
fi

echo "✅ Bitcoin regtest connection OK"

# Get current block height
BLOCK_HEIGHT=$(curl -s -u "$RPC_USER:$RPC_PASS" \
               -d '{"jsonrpc":"1.0","id":"test","method":"getblockcount","params":[]}' \
               -H 'Content-Type: application/json' \
               "$RPC_URL" | jq -r '.result')

echo "📊 Current block height: $BLOCK_HEIGHT"

# Check wallet balance
BALANCE=$(curl -s -u "$RPC_USER:$RPC_PASS" \
          -d '{"jsonrpc":"1.0","id":"test","method":"getbalance","params":[]}' \
          -H 'Content-Type: application/json' \
          "$RPC_URL" | jq -r '.result')

echo "💰 Wallet balance: $BALANCE BTC"

if (( $(echo "$BALANCE < 1" | bc -l) )); then
    echo "💰 Generating more blocks for funding..."
    curl -s -u "$RPC_USER:$RPC_PASS" \
         -d '{"jsonrpc":"1.0","id":"test","method":"generate","params":[10]}' \
         -H 'Content-Type: application/json' \
         "$RPC_URL" > /dev/null
    
    BALANCE=$(curl -s -u "$RPC_USER:$RPC_PASS" \
              -d '{"jsonrpc":"1.0","id":"test","method":"getbalance","params":[]}' \
              -H 'Content-Type: application/json' \
              "$RPC_URL" | jq -r '.result')
    echo "💰 New balance: $BALANCE BTC"
fi

# Generate simple BTCFi CREATE transaction parameters
TIMESTAMP=$(date +%s)
OPTION_ID=$(printf "%08x" $((RANDOM * 65536 + RANDOM)))

# Simple CREATE schema - only essential fields
TX_TYPE="CREATE"
OPTION_TYPE="CALL"
STRIKE=52000
EXPIRY=$((TIMESTAMP + 7 * 24 * 3600))  # 7 days from now
UNIT=1.0

# Convert to required formats
STRIKE_SATS=$((STRIKE * 100000000))

echo ""
echo "🎯 BTCFi CREATE Transaction:"
echo "   TX Type: $TX_TYPE"
echo "   Option ID: $OPTION_ID"
echo "   Option Type: $OPTION_TYPE"
echo "   Strike: $STRIKE USD ($STRIKE_SATS sats)"
echo "   Expiry: 7 days ($(date -r $EXPIRY 2>/dev/null || date -d @$EXPIRY 2>/dev/null))"
echo "   Unit: $UNIT"

# Create simple BTCFi CREATE schema OP_RETURN data
echo ""
echo "📝 Creating BTCFi CREATE schema OP_RETURN data..."

# Simple CREATE transaction schema - only essential data
OP_RETURN_DATA=""

# TX Type (1 byte): CREATE=0, BUY=1, SETTLE=2, CHALLENGE=3
OP_RETURN_DATA="${OP_RETURN_DATA}00"  # CREATE

# Option ID (6 bytes): simplified ID
OPTION_ID_SIMPLE=$(echo "$OPTION_ID" | sed 's/0x//' | tr '[:lower:]' '[:upper:]')
OPTION_ID_HEX=$(printf "%-12s" "$OPTION_ID_SIMPLE" | sed 's/ /0/g' | cut -c1-12)
OP_RETURN_DATA="${OP_RETURN_DATA}${OPTION_ID_HEX}"

# Option Type (1 byte): CALL=0, PUT=1
OP_RETURN_DATA="${OP_RETURN_DATA}00"  # CALL

# Strike (8 bytes, big endian)
STRIKE_HEX=$(printf "%016x" $STRIKE_SATS)
OP_RETURN_DATA="${OP_RETURN_DATA}${STRIKE_HEX}"

# Expiry (8 bytes, big endian)
EXPIRY_HEX=$(printf "%016x" $EXPIRY)
OP_RETURN_DATA="${OP_RETURN_DATA}${EXPIRY_HEX}"

# Unit (4 bytes): 1.0 as 32-bit float
UNIT_HEX="3f800000"  # IEEE 754 representation of 1.0
OP_RETURN_DATA="${OP_RETURN_DATA}${UNIT_HEX}"

echo "🔍 Debug values before encoding:"
echo "   TX Type: $TX_TYPE (00)"
echo "   Option ID: $OPTION_ID"
echo "   Option Type: $OPTION_TYPE (00)" 
echo "   Strike: $STRIKE USD = $STRIKE_SATS sats = $STRIKE_HEX hex"
echo "   Expiry: $EXPIRY timestamp = $EXPIRY_HEX hex"
echo "   Unit: $UNIT = $UNIT_HEX hex"

echo "📦 OP_RETURN data: $OP_RETURN_DATA"
echo "📏 Data length: $((${#OP_RETURN_DATA} / 2)) bytes"

# Create transaction
echo ""
echo "🔨 Creating transaction..."

# Get a new address for change
CHANGE_ADDRESS=$(curl -s -u "$RPC_USER:$RPC_PASS" \
                 -d '{"jsonrpc":"1.0","id":"test","method":"getnewaddress","params":["option_change"]}' \
                 -H 'Content-Type: application/json' \
                 "$RPC_URL" | jq -r '.result')

echo "🏠 Change address: $CHANGE_ADDRESS"

# Create transaction with OP_RETURN output
RAW_TX=$(curl -s -u "$RPC_USER:$RPC_PASS" \
         -d "{\"jsonrpc\":\"1.0\",\"id\":\"test\",\"method\":\"createrawtransaction\",\"params\":[[],{\"data\":\"$OP_RETURN_DATA\",\"$CHANGE_ADDRESS\":0.001}]}" \
         -H 'Content-Type: application/json' \
         "$RPC_URL" | jq -r '.result')

# Fund the transaction
FUNDED_TX_RESULT=$(curl -s -u "$RPC_USER:$RPC_PASS" \
                   -d "{\"jsonrpc\":\"1.0\",\"id\":\"test\",\"method\":\"fundrawtransaction\",\"params\":[\"$RAW_TX\"]}" \
                   -H 'Content-Type: application/json' \
                   "$RPC_URL" | jq -r '.result')

FUNDED_TX=$(echo "$FUNDED_TX_RESULT" | jq -r '.hex')
TX_FEE=$(echo "$FUNDED_TX_RESULT" | jq -r '.fee')

echo "💸 Transaction fee: $TX_FEE BTC"

# Sign the transaction
SIGNED_TX_RESULT=$(curl -s -u "$RPC_USER:$RPC_PASS" \
                   -d "{\"jsonrpc\":\"1.0\",\"id\":\"test\",\"method\":\"signrawtransactionwithwallet\",\"params\":[\"$FUNDED_TX\"]}" \
                   -H 'Content-Type: application/json' \
                   "$RPC_URL" | jq -r '.result')

SIGNED_TX=$(echo "$SIGNED_TX_RESULT" | jq -r '.hex')
TX_COMPLETE=$(echo "$SIGNED_TX_RESULT" | jq -r '.complete')

if [ "$TX_COMPLETE" != "true" ]; then
    echo "❌ Failed to sign transaction"
    exit 1
fi

echo "✍️  Transaction signed successfully"

# Send the transaction (no confirmation needed for regtest)
echo "📡 Broadcasting transaction..."

TXID=$(curl -s -u "$RPC_USER:$RPC_PASS" \
       -d "{\"jsonrpc\":\"1.0\",\"id\":\"test\",\"method\":\"sendrawtransaction\",\"params\":[\"$SIGNED_TX\"]}" \
       -H 'Content-Type: application/json' \
       "$RPC_URL" | jq -r '.result')

if [ "$TXID" = "null" ] || [ -z "$TXID" ]; then
    echo "❌ Failed to send transaction"
    curl -s -u "$RPC_USER:$RPC_PASS" \
         -d "{\"jsonrpc\":\"1.0\",\"id\":\"test\",\"method\":\"sendrawtransaction\",\"params\":[\"$SIGNED_TX\"]}" \
         -H 'Content-Type: application/json' \
         "$RPC_URL" | jq '.error'
    exit 1
fi

echo "🎉 Option registered successfully!"

# Generate a block to confirm transaction
echo "⛏️  Mining block to confirm transaction..."
curl -s -u "$RPC_USER:$RPC_PASS" \
     -d '{"jsonrpc":"1.0","id":"test","method":"generate","params":[1]}' \
     -H 'Content-Type: application/json' \
     "$RPC_URL" > /dev/null

# Get transaction info
TX_INFO=$(curl -s -u "$RPC_USER:$RPC_PASS" \
          -d "{\"jsonrpc\":\"1.0\",\"id\":\"test\",\"method\":\"gettransaction\",\"params\":[\"$TXID\"]}" \
          -H 'Content-Type: application/json' \
          "$RPC_URL" | jq -r '.result')

CONFIRMATIONS=$(echo "$TX_INFO" | jq -r '.confirmations')
BLOCK_HASH=$(echo "$TX_INFO" | jq -r '.blockhash')

echo ""
echo "📋 Registration Summary:"
echo "   Transaction ID: $TXID"
echo "   Confirmations: $CONFIRMATIONS"
echo "   Block Hash: $BLOCK_HASH"
echo "   Option ID: $OPTION_ID"
echo "   Strike: \$$STRIKE_USD"
echo "   Premium: \$$PREMIUM_USD"
echo "   Expiry: 7 days"
echo ""
echo "🔍 Verify transaction:"
echo "   Raw TX: $SIGNED_TX"
echo "   OP_RETURN data: $OP_RETURN_DATA"
echo ""
echo "🎉 Option registration completed and confirmed!"

# Decode the transaction to show OP_RETURN
echo ""
echo "📜 Transaction details:"
curl -s -u "$RPC_USER:$RPC_PASS" \
     -d "{\"jsonrpc\":\"1.0\",\"id\":\"test\",\"method\":\"decoderawtransaction\",\"params\":[\"$SIGNED_TX\"]}" \
     -H 'Content-Type: application/json' \
     "$RPC_URL" | jq '.result.vout[] | select(.scriptPubKey.type == "nulldata") | .scriptPubKey.asm'