#!/bin/bash

# BTCFi Oracle - 여러 Binance Oracle Node 실행 스크립트 (1분 간격)

echo "🚀 Starting multiple Binance Oracle Nodes (1-minute interval)..."

# 터미널별로 Oracle Node 실행
echo "📋 Available commands:"
echo "  1. Run all nodes in background"
echo "  2. Run individual nodes in separate terminals"
echo

read -p "Choose option (1 or 2): " choice

case $choice in
    1)
        echo "🔄 Starting all Binance nodes in background..."
        
        # Binance Node 1
        echo "Starting Binance Oracle Node 1..."
        cargo run -p oracle-node -- --node-id "oracle-binance-node-1" --interval 60 &
        BINANCE1_PID=$!
        
        # Binance Node 2  
        echo "Starting Binance Oracle Node 2..."
        cargo run -p oracle-node -- --node-id "oracle-binance-node-2" --interval 60 &
        BINANCE2_PID=$!
        
        # Binance Node 3
        echo "Starting Binance Oracle Node 3..."
        cargo run -p oracle-node -- --node-id "oracle-binance-node-3" --interval 60 &
        BINANCE3_PID=$!
        
        echo "✅ All Binance nodes started!"
        echo "Binance Node 1 PID: $BINANCE1_PID"
        echo "Binance Node 2 PID: $BINANCE2_PID"
        echo "Binance Node 3 PID: $BINANCE3_PID"
        echo
        echo "🔍 Each node fetches BTC price from Binance every 60 seconds"
        echo "📊 Aggregator will calculate average price from all nodes"
        echo
        echo "Press Ctrl+C to stop all nodes..."
        
        # Wait for interrupt
        trap "echo 'Stopping all nodes...'; kill $BINANCE1_PID $BINANCE2_PID $BINANCE3_PID 2>/dev/null; exit" INT
        wait
        ;;
        
    2)
        echo "🖥️ Run these commands in separate terminals:"
        echo
        echo "Terminal 1 (Aggregator):"
        echo "  cargo run -p aggregator"
        echo
        echo "Terminal 2 (Binance Node 1):"
        echo "  cargo run -p oracle-node -- --node-id 'oracle-binance-node-1' --interval 60"
        echo
        echo "Terminal 3 (Binance Node 2):"  
        echo "  cargo run -p oracle-node -- --node-id 'oracle-binance-node-2' --interval 60"
        echo
        echo "Terminal 4 (Binance Node 3):"
        echo "  cargo run -p oracle-node -- --node-id 'oracle-binance-node-3' --interval 60"
        echo
        echo "Terminal 5 (Additional Node):"
        echo "  cargo run -p oracle-node -- --node-id 'oracle-binance-node-4' --interval 60"
        ;;
        
    *)
        echo "❌ Invalid option"
        exit 1
        ;;
esac