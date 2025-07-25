#!/bin/bash

# Decode BTCFi Option OP_RETURN Data
# Based on Price Anchoring Branch implementation

if [ -z "$1" ]; then
    echo "Usage: $0 <transaction_id>"
    exit 1
fi

TXID="$1"
RPC_USER="test"
RPC_PASS="test"
RPC_CONNECT="localhost:18443"

# Get raw transaction
RAW_TX=$(bitcoin-cli -regtest -rpcuser="$RPC_USER" -rpcpassword="$RPC_PASS" -rpcconnect="$RPC_CONNECT" \
    getrawtransaction "$TXID" true 2>/dev/null)

if [ -z "$RAW_TX" ] || [ "$RAW_TX" = "null" ]; then
    echo "❌ Transaction not found: $TXID"
    exit 1
fi

# Extract OP_RETURN data
OP_RETURN_HEX=$(echo "$RAW_TX" | jq -r '.vout[] | select(.scriptPubKey.type == "nulldata") | .scriptPubKey.hex' | head -1)

if [ -z "$OP_RETURN_HEX" ] || [ "$OP_RETURN_HEX" = "null" ]; then
    echo "❌ No OP_RETURN data found"
    exit 1
fi

# Remove OP_RETURN prefix (6a1c = OP_RETURN + push 28 bytes)
OP_RETURN_DATA=$(echo "$OP_RETURN_HEX" | cut -c5-)

# Parse BTCFi CREATE data (28 bytes)
TX_TYPE_HEX=$(echo "$OP_RETURN_DATA" | cut -c1-2)
OPTION_ID_HEX=$(echo "$OP_RETURN_DATA" | cut -c3-14)
OPTION_TYPE_HEX=$(echo "$OP_RETURN_DATA" | cut -c15-16)
STRIKE_HEX=$(echo "$OP_RETURN_DATA" | cut -c17-32)
EXPIRY_HEX=$(echo "$OP_RETURN_DATA" | cut -c33-48)
UNIT_HEX=$(echo "$OP_RETURN_DATA" | cut -c49-56)

# Convert values
case "$TX_TYPE_HEX" in
    "00") TX_TYPE_TEXT="CREATE" ;;
    "01") TX_TYPE_TEXT="BUY" ;;
    "02") TX_TYPE_TEXT="SETTLE" ;;
    "03") TX_TYPE_TEXT="CHALLENGE" ;;
    *) TX_TYPE_TEXT="Unknown ($TX_TYPE_HEX)" ;;
esac

case "$OPTION_TYPE_HEX" in
    "00") OPTION_TYPE_TEXT="CALL" ;;
    "01") OPTION_TYPE_TEXT="PUT" ;;
    *) OPTION_TYPE_TEXT="Unknown ($OPTION_TYPE_HEX)" ;;
esac

# Convert strike from hex to decimal (satoshis)
STRIKE_SATS=$(printf "%d" "0x$STRIKE_HEX")
STRIKE_USD=$((STRIKE_SATS / 100000000))

# Convert expiry timestamp
EXPIRY_TIMESTAMP=$(printf "%d" "0x$EXPIRY_HEX")
EXPIRY_DATE=$(date -r $EXPIRY_TIMESTAMP 2>/dev/null || date -d @$EXPIRY_TIMESTAMP 2>/dev/null || echo "Invalid date")

# Convert unit (IEEE 754 float) using Python
UNIT_FLOAT=$(python3 -c "
import struct
hex_bytes = bytes.fromhex('$UNIT_HEX')
float_val = struct.unpack('>f', hex_bytes)[0]
print(f'{float_val:.1f}')
" 2>/dev/null || echo "1.0")

# Get confirmations
CONFIRMATIONS=$(echo "$RAW_TX" | jq -r '.confirmations // 0')

echo "📊 BTCFi Option Data:"
echo "─────────────────────"
echo "📝 TX Type: $TX_TYPE_TEXT"
echo "🆔 Option ID Hash: $OPTION_ID_HEX"
echo "📈 Option Type: $OPTION_TYPE_TEXT"
echo "💰 Strike Price: \$$STRIKE_USD USD ($STRIKE_SATS sats)"
echo "📦 Unit: $UNIT_FLOAT"
echo "⏰ Expiry: $EXPIRY_DATE"
echo "✅ Confirmations: $CONFIRMATIONS"
echo ""
echo "🔍 Raw Data:"
echo "   Full OP_RETURN: $OP_RETURN_DATA"
echo "   Length: $((${#OP_RETURN_DATA} / 2)) bytes"