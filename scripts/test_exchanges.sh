#!/bin/bash

# BTCFi Oracle - 거래소별 개별 테스트 스크립트

echo "🧪 Testing individual exchange clients..."
echo "========================================"

# 각 거래소 개별 테스트 (1회씩만)
EXCHANGES=("binance" "coinbase" "kraken")

for exchange in "${EXCHANGES[@]}"; do
    echo ""
    echo "🔍 Testing $exchange client..."
    echo "Command: cargo run -p oracle-node -- --exchange $exchange --interval 5"
    echo "Press Enter to continue or Ctrl+C to skip..."
    read
    
    timeout 15s cargo run -p oracle-node -- --exchange $exchange --interval 5 || {
        echo "⚠️  Test for $exchange finished (timeout or manual stop)"
    }
done

echo ""
echo "✅ All exchange tests completed!"
echo "💡 If any exchange failed, check the error messages above"