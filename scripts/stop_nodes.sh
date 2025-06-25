#!/bin/bash

# BTCFi Oracle - 노드 중지 스크립트

echo "🛑 Stopping all Oracle Nodes..."

# Oracle Node 프로세스들 찾아서 종료
ORACLE_PIDS=$(pgrep -f "oracle-node")

if [ -z "$ORACLE_PIDS" ]; then
    echo "📭 No Oracle Node processes found"
else
    echo "🔍 Found Oracle Node processes: $ORACLE_PIDS"
    
    for PID in $ORACLE_PIDS; do
        echo "⏹️  Stopping process $PID..."
        kill $PID
        
        # 프로세스가 완전히 종료될 때까지 대기
        while kill -0 $PID 2>/dev/null; do
            sleep 0.1
        done
        
        echo "✅ Process $PID stopped"
    done
fi

echo ""
echo "🧹 Cleaning up..."

# 백그라운드 작업들도 정리
jobs -p | xargs -r kill 2>/dev/null

echo "✅ All Oracle Nodes stopped successfully!"
echo ""
echo "📊 Log files are preserved in logs/ directory"