#!/usr/bin/env python3
"""
gRPC Aggregator 테스트 클라이언트
"""

import grpc
import sys
import os

# proto 파일에서 생성된 모듈 import
try:
    import oracle_pb2
    import oracle_pb2_grpc
except ImportError:
    print("❌ Error: oracle_pb2 modules not found")
    print("💡 Hint: You need to generate Python gRPC stubs from oracle.proto")
    print("   protoc --python_out=. --grpc_python_out=. proto/oracle.proto")
    sys.exit(1)

def test_aggregator():
    """Aggregator 테스트"""
    channel = grpc.insecure_channel('localhost:50051')
    stub = oracle_pb2_grpc.OracleServiceStub(channel)
    
    try:
        # Health Check
        print("🔍 Testing Aggregator health...")
        health_request = oracle_pb2.HealthRequest(node_id="test-client")
        health_response = stub.HealthCheck(health_request)
        
        print(f"✅ Health: {health_response.healthy}")
        print(f"📊 Active nodes: {health_response.active_nodes}")
        print(f"🕐 Timestamp: {health_response.timestamp}")
        print(f"📦 Version: {health_response.version}")
        print()
        
        # Get Aggregated Price
        print("💰 Getting aggregated price...")
        price_request = oracle_pb2.GetPriceRequest()
        price_response = stub.GetAggregatedPrice(price_request)
        
        if price_response.success:
            print(f"✅ Success: {price_response.success}")
            print(f"💵 Aggregated Price: ${price_response.aggregated_price:.2f}")
            print(f"📈 Data Points: {price_response.data_points}")
            print(f"🕐 Last Update: {price_response.last_update}")
            print()
            
            print("📋 Recent prices:")
            for i, price_data in enumerate(price_response.recent_prices, 1):
                print(f"  {i}. ${price_data.price:.2f} from {price_data.source} (node: {price_data.node_id})")
        else:
            print("❌ Failed to get aggregated price")
            
    except grpc.RpcError as e:
        print(f"❌ gRPC Error: {e.code()} - {e.details()}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    channel.close()

if __name__ == "__main__":
    print("🚀 Testing BTCFi Oracle Aggregator...")
    print("=" * 50)
    test_aggregator()