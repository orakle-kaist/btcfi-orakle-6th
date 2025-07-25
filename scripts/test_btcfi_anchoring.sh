#!/bin/bash

# BTCFi Protocol Option Registration Test
# Based on Price Anchoring Branch exact implementation

set -e

echo "🚀 BTCFi Option Registration Test (Regtest)"
echo "=========================================="

# Bitcoin regtest configuration
RPC_USER="test"
RPC_PASS="test"
RPC_CONNECT="localhost:18443"

# Check Bitcoin connection
echo "🔗 Checking Bitcoin regtest connection..."
if ! bitcoin-cli -regtest -rpcuser="$RPC_USER" -rpcpassword="$RPC_PASS" -rpcconnect="$RPC_CONNECT" getblockcount &> /dev/null; then
    echo "❌ Failed to connect to Bitcoin regtest"
    exit 1
fi

echo "✅ Bitcoin regtest connection OK"

# Get current block height and balance
BLOCK_HEIGHT=$(bitcoin-cli -regtest -rpcuser="$RPC_USER" -rpcpassword="$RPC_PASS" -rpcconnect="$RPC_CONNECT" getblockcount)
BALANCE=$(bitcoin-cli -regtest -rpcuser="$RPC_USER" -rpcpassword="$RPC_PASS" -rpcconnect="$RPC_CONNECT" getbalance)

echo "📊 Current block height: $BLOCK_HEIGHT"
echo "💰 Wallet balance: $BALANCE BTC"

# Test Case 1: CALL Option
echo ""
echo "=== Test Case 1: CALL Option Registration ==="

# Generate option parameters
TIMESTAMP=$(date +%s)
OPTION_ID="BTCCALL52000D_7"  # BTC CALL $52,000 7 days
STRIKE_USD=52000
EXPIRY=$((TIMESTAMP + 7 * 24 * 3600))  # 7 days from now

# Create data using exact BTCFi protocol (28 bytes)
echo "📝 Creating BTCFi CREATE transaction data..."

# TX Type (1 byte): CREATE=00
TX_TYPE="00"

# Option ID (6 bytes): SHA256 hash truncated
OPTION_ID_HASH=$(echo -n "$OPTION_ID" | sha256sum | cut -c1-12)

# Option Type (1 byte): CALL=00
OPTION_TYPE="00"

# Strike (8 bytes, big-endian): Convert USD to satoshis
STRIKE_SATS=$((STRIKE_USD * 100000000))
STRIKE_HEX=$(printf "%016x" $STRIKE_SATS)

# Expiry (8 bytes, big-endian)
EXPIRY_HEX=$(printf "%016x" $EXPIRY)

# Unit (4 bytes): 1.0 as IEEE 754 float
UNIT_HEX="3f800000"

# Combine all data
OP_RETURN_DATA="${TX_TYPE}${OPTION_ID_HASH}${OPTION_TYPE}${STRIKE_HEX}${EXPIRY_HEX}${UNIT_HEX}"

echo "🔍 Data components:"
echo "   TX Type: CREATE ($TX_TYPE)"
echo "   Option ID: $OPTION_ID → Hash: $OPTION_ID_HASH"
echo "   Option Type: CALL ($OPTION_TYPE)"
echo "   Strike: $STRIKE_USD USD → $STRIKE_SATS sats → $STRIKE_HEX"
echo "   Expiry: $(date -r $EXPIRY 2>/dev/null || date -d @$EXPIRY) → $EXPIRY_HEX"
echo "   Unit: 1.0 → $UNIT_HEX"
echo "📦 Complete OP_RETURN data: $OP_RETURN_DATA"
echo "📏 Data length: $((${#OP_RETURN_DATA} / 2)) bytes (should be 28)"

# Get change address
CHANGE_ADDRESS=$(bitcoin-cli -regtest -rpcuser="$RPC_USER" -rpcpassword="$RPC_PASS" -rpcconnect="$RPC_CONNECT" getnewaddress "option_change")

# Create, fund, sign, and send transaction
echo ""
echo "🔨 Creating and sending transaction..."

# Create raw transaction
RAW_TX=$(bitcoin-cli -regtest -rpcuser="$RPC_USER" -rpcpassword="$RPC_PASS" -rpcconnect="$RPC_CONNECT" \
    createrawtransaction '[]' "{\"data\":\"$OP_RETURN_DATA\",\"$CHANGE_ADDRESS\":0.001}")

# Fund transaction
FUNDED_TX=$(bitcoin-cli -regtest -rpcuser="$RPC_USER" -rpcpassword="$RPC_PASS" -rpcconnect="$RPC_CONNECT" \
    fundrawtransaction "$RAW_TX" | jq -r .hex)

# Sign transaction
SIGNED_TX=$(bitcoin-cli -regtest -rpcuser="$RPC_USER" -rpcpassword="$RPC_PASS" -rpcconnect="$RPC_CONNECT" \
    signrawtransactionwithwallet "$FUNDED_TX" | jq -r .hex)

# Send transaction
TXID=$(bitcoin-cli -regtest -rpcuser="$RPC_USER" -rpcpassword="$RPC_PASS" -rpcconnect="$RPC_CONNECT" \
    sendrawtransaction "$SIGNED_TX")

echo "✅ Transaction sent! TXID: $TXID"

# Mine a block to confirm
echo "⛏️  Mining block to confirm..."
bitcoin-cli -regtest -rpcuser="$RPC_USER" -rpcpassword="$RPC_PASS" -rpcconnect="$RPC_CONNECT" -generate 1 > /dev/null

# Verify the transaction
echo ""
echo "🔍 Verifying transaction..."

# Get raw transaction
TX_DATA=$(bitcoin-cli -regtest -rpcuser="$RPC_USER" -rpcpassword="$RPC_PASS" -rpcconnect="$RPC_CONNECT" \
    getrawtransaction "$TXID" true)

# Extract OP_RETURN hex
OP_RETURN_HEX=$(echo "$TX_DATA" | jq -r '.vout[] | select(.scriptPubKey.type == "nulldata") | .scriptPubKey.hex')

echo "📦 OP_RETURN hex from chain: $OP_RETURN_HEX"

# Decode the data (remove 6a1c prefix - OP_RETURN + push 28 bytes)
DECODED_DATA=$(echo "$OP_RETURN_HEX" | cut -c5-)
echo "📦 Decoded data: $DECODED_DATA"

# Test Case 2: PUT Option
echo ""
echo "=== Test Case 2: PUT Option Registration ==="

OPTION_ID_PUT="BTCPUT48000D_14"  # BTC PUT $48,000 14 days
STRIKE_USD_PUT=48000
EXPIRY_PUT=$((TIMESTAMP + 14 * 24 * 3600))  # 14 days

# Create PUT option data
OPTION_ID_HASH_PUT=$(echo -n "$OPTION_ID_PUT" | sha256sum | cut -c1-12)
OPTION_TYPE_PUT="01"  # PUT
STRIKE_SATS_PUT=$((STRIKE_USD_PUT * 100000000))
STRIKE_HEX_PUT=$(printf "%016x" $STRIKE_SATS_PUT)
EXPIRY_HEX_PUT=$(printf "%016x" $EXPIRY_PUT)

OP_RETURN_DATA_PUT="${TX_TYPE}${OPTION_ID_HASH_PUT}${OPTION_TYPE_PUT}${STRIKE_HEX_PUT}${EXPIRY_HEX_PUT}${UNIT_HEX}"

echo "📝 PUT Option Data:"
echo "   Option ID: $OPTION_ID_PUT → Hash: $OPTION_ID_HASH_PUT"
echo "   Option Type: PUT ($OPTION_TYPE_PUT)"
echo "   Strike: $STRIKE_USD_PUT USD"
echo "   Expiry: 14 days"

# Create and send PUT transaction
RAW_TX_PUT=$(bitcoin-cli -regtest -rpcuser="$RPC_USER" -rpcpassword="$RPC_PASS" -rpcconnect="$RPC_CONNECT" \
    createrawtransaction '[]' "{\"data\":\"$OP_RETURN_DATA_PUT\",\"$CHANGE_ADDRESS\":0.001}")

FUNDED_TX_PUT=$(bitcoin-cli -regtest -rpcuser="$RPC_USER" -rpcpassword="$RPC_PASS" -rpcconnect="$RPC_CONNECT" \
    fundrawtransaction "$RAW_TX_PUT" | jq -r .hex)

SIGNED_TX_PUT=$(bitcoin-cli -regtest -rpcuser="$RPC_USER" -rpcpassword="$RPC_PASS" -rpcconnect="$RPC_CONNECT" \
    signrawtransactionwithwallet "$FUNDED_TX_PUT" | jq -r .hex)

TXID_PUT=$(bitcoin-cli -regtest -rpcuser="$RPC_USER" -rpcpassword="$RPC_PASS" -rpcconnect="$RPC_CONNECT" \
    sendrawtransaction "$SIGNED_TX_PUT")

echo "✅ PUT Option registered! TXID: $TXID_PUT"

# Mine block
bitcoin-cli -regtest -rpcuser="$RPC_USER" -rpcpassword="$RPC_PASS" -rpcconnect="$RPC_CONNECT" -generate 1 > /dev/null

# Decode both transactions
echo ""
echo "=== Decoding Results ==="
echo ""
echo "📋 CALL Option ($TXID):"
./scripts/decode_btcfi_option.sh "$TXID"

echo ""
echo "📋 PUT Option ($TXID_PUT):"
./scripts/decode_btcfi_option.sh "$TXID_PUT"

echo ""
echo "✅ BTCFi Protocol Test Complete!"