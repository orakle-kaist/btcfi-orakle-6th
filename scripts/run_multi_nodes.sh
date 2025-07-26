#!/bin/bash

# BTCFi Oracle - 다중 노드 실행 스크립트
# 3개의 거래소에서 동시에 가격 수집

echo "🚀 Starting BTCFi Oracle Multi-Node System (60sec intervals)..."
echo "=============================================================="

# Aggregator가 실행 중인지 확인
if ! pgrep -f "aggregator" > /dev/null; then
    echo "❌ Aggregator is not running!"
    echo "💡 Please start the aggregator first: cargo run -p aggregator"
    exit 1
fi

echo "✅ Aggregator is running"
echo ""

# 로그 디렉토리 생성
mkdir -p logs

# Node 1: Binance
echo "🟡 Starting Oracle Node 1 (Binance) - 60sec interval..."
cargo run -p oracle-node -- --exchange binance --node-id oracle-node-1 --interval 60 > logs/node1_binance.log 2>&1 &
NODE1_PID=$!

sleep 2

# Node 2: Coinbase  
echo "🔵 Starting Oracle Node 2 (Coinbase) - 60sec interval..."
cargo run -p oracle-node -- --exchange coinbase --node-id oracle-node-2 --interval 60 > logs/node2_coinbase.log 2>&1 &
NODE2_PID=$!

sleep 2

# Node 3: Kraken
echo "🟠 Starting Oracle Node 3 (Kraken) - 60sec interval..."
cargo run -p oracle-node -- --exchange kraken --node-id oracle-node-3 --interval 60 > logs/node3_kraken.log 2>&1 &
NODE3_PID=$!

echo ""
echo "🎯 All Oracle Nodes started successfully!"
echo "Node 1 (Binance): PID $NODE1_PID"
echo "Node 2 (Coinbase): PID $NODE2_PID" 
echo "Node 3 (Kraken): PID $NODE3_PID"
echo ""
echo "📊 Logs available at:"
echo "  - logs/node1_binance.log"
echo "  - logs/node2_coinbase.log"
echo "  - logs/node3_kraken.log"
echo ""
echo "🔍 To monitor in real-time:"
echo "  tail -f logs/node1_binance.log"
echo "  tail -f logs/node2_coinbase.log"
echo "  tail -f logs/node3_kraken.log"
echo ""
echo "⏹️  To stop all nodes: ./scripts/stop_nodes.sh"
echo "📈 To test aggregator: python3 scripts/test_aggregator.py"
echo ""
echo "Press Ctrl+C to stop monitoring..."

# 노드들이 계속 실행되도록 대기
wait