#!/bin/bash

# Bitcoin Docker Management Script

REGTEST_RPC="http://bitcoinrpc:rpcpassword@localhost:18443"
TESTNET_RPC="http://bitcoinrpc:rpcpassword@localhost:18332"

case "$1" in
    "regtest")
        echo "🚀 Starting Bitcoin Regtest node..."
        docker-compose -f docker-compose.bitcoin.yml up -d bitcoin-regtest
        
        echo "⏳ Waiting for node to start..."
        sleep 10
        
        echo "🏠 Creating wallet..."
        docker exec bitcoin-regtest bitcoin-cli -regtest createwallet "testwallet" || echo "Wallet may already exist"
        
        echo "⛏️  Generating initial blocks (101 blocks = 50 BTC)..."
        docker exec bitcoin-regtest bitcoin-cli -regtest generate 101
        
        echo "💰 Wallet balance:"
        docker exec bitcoin-regtest bitcoin-cli -regtest getbalance
        
        echo "✅ Bitcoin Regtest ready!"
        echo "📊 RPC URL: $REGTEST_RPC"
        ;;
        
    "testnet")
        echo "🌐 Starting Bitcoin Testnet node..."
        docker-compose -f docker-compose.bitcoin.yml --profile testnet up -d bitcoin-testnet
        
        echo "⏳ Waiting for node to start..."
        sleep 15
        
        echo "🏠 Creating wallet..."
        docker exec bitcoin-testnet bitcoin-cli -testnet createwallet "testwallet" || echo "Wallet may already exist"
        
        echo "📡 Getting new address for testnet coins:"
        docker exec bitcoin-testnet bitcoin-cli -testnet getnewaddress
        
        echo "💡 Get testnet coins from: https://coinfaucet.eu/en/btc-testnet/"
        echo "✅ Bitcoin Testnet ready!"
        echo "📊 RPC URL: $TESTNET_RPC"
        ;;
        
    "stop")
        echo "🛑 Stopping Bitcoin nodes..."
        docker-compose -f docker-compose.bitcoin.yml down
        ;;
        
    "logs")
        if [ "$2" = "testnet" ]; then
            docker logs -f bitcoin-testnet
        else
            docker logs -f bitcoin-regtest
        fi
        ;;
        
    "status")
        echo "📊 Bitcoin Node Status:"
        echo ""
        
        if docker ps | grep -q bitcoin-regtest; then
            echo "🟢 Regtest: Running"
            echo "   Balance: $(docker exec bitcoin-regtest bitcoin-cli -regtest getbalance 2>/dev/null || echo 'Error')"
            echo "   Blocks: $(docker exec bitcoin-regtest bitcoin-cli -regtest getblockcount 2>/dev/null || echo 'Error')"
        else
            echo "🔴 Regtest: Stopped"
        fi
        
        if docker ps | grep -q bitcoin-testnet; then
            echo "🟢 Testnet: Running"
            echo "   Balance: $(docker exec bitcoin-testnet bitcoin-cli -testnet getbalance 2>/dev/null || echo 'Error')"
            echo "   Blocks: $(docker exec bitcoin-testnet bitcoin-cli -testnet getblockchaininfo 2>/dev/null | jq -r '.blocks' || echo 'Error')"
        else
            echo "🔴 Testnet: Stopped"
        fi
        ;;
        
    "cli")
        if [ "$2" = "testnet" ]; then
            docker exec -it bitcoin-testnet bitcoin-cli -testnet "${@:3}"
        else
            docker exec -it bitcoin-regtest bitcoin-cli -regtest "${@:3}"
        fi
        ;;
        
    *)
        echo "Bitcoin Docker Management"
        echo "========================"
        echo ""
        echo "Usage: $0 <command> [options]"
        echo ""
        echo "Commands:"
        echo "  regtest          Start Bitcoin regtest node (fast, local testing)"
        echo "  testnet          Start Bitcoin testnet node (real network)"
        echo "  stop             Stop all Bitcoin nodes"
        echo "  status           Show status of all nodes"
        echo "  logs [testnet]   Show logs (default: regtest)"
        echo "  cli [testnet] <cmd>  Run bitcoin-cli command"
        echo ""
        echo "Examples:"
        echo "  $0 regtest                    # Start regtest with 50 BTC"
        echo "  $0 cli getbalance            # Check regtest balance"
        echo "  $0 cli testnet getbalance    # Check testnet balance"
        echo "  $0 cli generate 1            # Generate 1 block (regtest only)"
        ;;
esac