#!/bin/bash

# Decode BTCFi Option OP_RETURN Data
# This script parses and displays option product data from Bitcoin transactions

if [ -z "$1" ]; then
    echo "Usage: $0 <transaction_id> [rpc_url]"
    echo "Example: $0 f504c3cbb8909c26885af4adc414eadb80016b33619566599cf4359bbd8419a1"
    exit 1
fi

TXID="$1"
RPC_URL="${2:-http://localhost:18443}"
RPC_USER="bitcoinrpc"
RPC_PASS="rpcpassword"

echo "🔍 BTCFi Option Data Decoder"
echo "============================"
echo "Transaction ID: $TXID"
echo ""

# Get raw transaction
echo "📡 Fetching transaction data..."
RAW_TX=$(curl -s -u "$RPC_USER:$RPC_PASS" \
         -d "{\"jsonrpc\":\"1.0\",\"id\":\"test\",\"method\":\"getrawtransaction\",\"params\":[\"$TXID\", true]}" \
         -H 'Content-Type: application/json' \
         "$RPC_URL" | jq -r '.result')

if [ "$RAW_TX" = "null" ] || [ -z "$RAW_TX" ]; then
    echo "❌ Transaction not found"
    exit 1
fi

# Extract OP_RETURN data
echo "🔎 Searching for OP_RETURN output..."
OP_RETURN_HEX=$(echo "$RAW_TX" | jq -r '.vout[] | select(.scriptPubKey.type == "nulldata") | .scriptPubKey.hex' | head -1)

if [ "$OP_RETURN_HEX" = "null" ] || [ -z "$OP_RETURN_HEX" ]; then
    echo "❌ No OP_RETURN data found in transaction"
    exit 1
fi

# Remove OP_RETURN opcode (6a) and push length
OP_RETURN_DATA=$(echo "$OP_RETURN_HEX" | sed 's/^6a..//')

echo "📦 Raw OP_RETURN data: $OP_RETURN_DATA"
echo "📏 Data length: $((${#OP_RETURN_DATA} / 2)) bytes"
echo ""

# Parse BTCFi CREATE transaction data
echo "✅ BTCFi CREATE Transaction Detected"
echo "======================================"

# Parse simple CREATE schema (28 bytes total)
TX_TYPE_HEX=$(echo "$OP_RETURN_DATA" | cut -c1-2)       # TX Type (1 byte = 2 chars)
OPTION_ID_HEX=$(echo "$OP_RETURN_DATA" | cut -c3-14)    # Option ID (6 bytes = 12 chars)
OPTION_TYPE_HEX=$(echo "$OP_RETURN_DATA" | cut -c15-16) # Option Type (1 byte = 2 chars)
STRIKE_HEX=$(echo "$OP_RETURN_DATA" | cut -c17-32)      # Strike (8 bytes = 16 chars)
EXPIRY_HEX=$(echo "$OP_RETURN_DATA" | cut -c33-48)      # Expiry (8 bytes = 16 chars)
UNIT_HEX=$(echo "$OP_RETURN_DATA" | cut -c49-56)        # Unit (4 bytes = 8 chars)

echo "🔍 Debug hex values:"
echo "   TX Type: $TX_TYPE_HEX"
echo "   Option ID: $OPTION_ID_HEX"
echo "   Option Type: $OPTION_TYPE_HEX"
echo "   Strike: $STRIKE_HEX"
echo "   Expiry: $EXPIRY_HEX"
echo "   Unit: $UNIT_HEX"

# Convert hex to readable values
case "$TX_TYPE_HEX" in
    "00") TX_TYPE_TEXT="CREATE" ;;
    "01") TX_TYPE_TEXT="BUY" ;;
    "02") TX_TYPE_TEXT="SETTLE" ;;
    "03") TX_TYPE_TEXT="CHALLENGE" ;;
    *) TX_TYPE_TEXT="Unknown ($TX_TYPE_HEX)" ;;
esac

# Clean option ID (remove trailing zeros)
OPTION_ID_CLEAN=$(echo "$OPTION_ID_HEX" | sed 's/0*$//')
OPTION_ID_FORMATTED="$OPTION_ID_CLEAN"

case "$OPTION_TYPE_HEX" in
    "00") OPTION_TYPE_TEXT="CALL" ;;
    "01") OPTION_TYPE_TEXT="PUT" ;;
    *) OPTION_TYPE_TEXT="Unknown ($OPTION_TYPE_HEX)" ;;
esac

# Convert big-endian hex to decimal
STRIKE_SATS=$(python3 -c "print(int('$STRIKE_HEX', 16))")
EXPIRY_TIMESTAMP=$(python3 -c "print(int('$EXPIRY_HEX', 16))")

# Convert sats to USD
STRIKE_USD=$(python3 -c "print(f'{$STRIKE_SATS / 100000000:.2f}')")

# Convert IEEE 754 float
UNIT_FLOAT=$(python3 -c "
import struct
hex_bytes = bytes.fromhex('$UNIT_HEX')
float_val = struct.unpack('>f', hex_bytes)[0]
print(f'{float_val:.1f}')
")

echo "🔍 Converted values:"
echo "   TX Type: $TX_TYPE_TEXT"
echo "   Option ID: $OPTION_ID_FORMATTED"
echo "   Option Type: $OPTION_TYPE_TEXT" 
echo "   Strike: $STRIKE_USD USD ($STRIKE_SATS sats)"
echo "   Unit: $UNIT_FLOAT"
echo "   Expiry timestamp: $EXPIRY_TIMESTAMP"

# Convert timestamp to human readable
EXPIRY_DATE=$(date -r $EXPIRY_TIMESTAMP 2>/dev/null || date -d @$EXPIRY_TIMESTAMP 2>/dev/null || echo "Invalid date")

echo ""
echo "📊 BTCFi CREATE Transaction Data:"
echo "─────────────────────────────────"
echo "📝 TX Type: $TX_TYPE_TEXT"
echo "🆔 Option ID: $OPTION_ID_FORMATTED" 
echo "📈 Option Type: $OPTION_TYPE_TEXT"
echo "💰 Strike Price: $STRIKE_USD USD ($STRIKE_SATS sats)"
echo "📦 Unit: $UNIT_FLOAT"
echo "⏰ Expiry: $EXPIRY_DATE ($EXPIRY_TIMESTAMP)"
echo ""

# Get transaction confirmation details
CONFIRMATIONS=$(echo "$RAW_TX" | jq -r '.confirmations // 0')
BLOCK_HASH=$(echo "$RAW_TX" | jq -r '.blockhash // "unconfirmed"')
BLOCK_HEIGHT=$(echo "$RAW_TX" | jq -r '.blockheight // "pending"')
TX_SIZE=$(echo "$RAW_TX" | jq -r '.size')
TX_FEE=$(echo "$RAW_TX" | jq -r '.fee // "unknown"')

echo "⛓️  Blockchain Info:"
echo "   Confirmations: $CONFIRMATIONS"
echo "   Block Hash: $BLOCK_HASH"
echo "   Block Height: $BLOCK_HEIGHT"
echo "   Transaction Size: $TX_SIZE bytes"
echo "   Fee: $TX_FEE BTC"
echo ""

# Calculate days until expiry
CURRENT_TIME=$(date +%s)
DAYS_UNTIL_EXPIRY=$(python3 -c "print(max(0, ($EXPIRY_TIMESTAMP - $CURRENT_TIME) // 86400))")

if [ "$DAYS_UNTIL_EXPIRY" -gt 0 ]; then
    echo "⏰ Time until expiry: $DAYS_UNTIL_EXPIRY days"
else
    echo "⚠️  Option has expired"
fi

# Show all transaction outputs for context
echo ""
echo "📋 Transaction Outputs:"
echo "───────────────────────"
echo "$RAW_TX" | jq -r '.vout[] | "Output \(.n): \(.value) BTC (\(.scriptPubKey.type))"'

echo ""
echo "✅ Decoding completed!"