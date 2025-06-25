#!/usr/bin/env python3
"""
Mock Aggregator for Testing Oracle Node
간단한 테스트용 Aggregator 서버
"""

from flask import Flask, request, jsonify
from datetime import datetime
import json

app = Flask(__name__)

# 받은 가격 데이터를 저장할 리스트
price_data_list = []

@app.route('/health', methods=['GET'])
def health():
    """헬스체크 엔드포인트"""
    return jsonify({
        "status": "healthy",
        "timestamp": int(datetime.now().timestamp()),
        "active_nodes": len(set(data.get('node_id') for data in price_data_list[-10:]))
    })

@app.route('/submit-price', methods=['POST'])
def submit_price():
    """Oracle Node로부터 가격 데이터 받기"""
    try:
        data = request.get_json()
        
        # 필수 필드 검증
        required_fields = ['price', 'timestamp', 'source', 'node_id']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    "status": "error",
                    "message": f"Missing required field: {field}"
                }), 400
        
        # 가격 검증
        price = data['price']
        if not isinstance(price, (int, float)) or price <= 0:
            return jsonify({
                "status": "error",
                "message": "Invalid price data",
                "details": "Price must be positive number"
            }), 400
        
        # 데이터 저장
        price_data_list.append({
            **data,
            "received_at": datetime.now().isoformat()
        })
        
        # 최근 100개만 보관
        if len(price_data_list) > 100:
            price_data_list.pop(0)
        
        # 집계된 가격 계산 (단순히 최근 5개의 평균)
        recent_prices = [item['price'] for item in price_data_list[-5:]]
        aggregated_price = sum(recent_prices) / len(recent_prices)
        
        print(f"📨 Received price: ${price:.2f} from {data['source']} (node: {data['node_id']})")
        print(f"📊 Aggregated price: ${aggregated_price:.2f}")
        
        return jsonify({
            "status": "success",
            "message": "Price data received",
            "aggregated_price": round(aggregated_price, 2)
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Server error",
            "details": str(e)
        }), 500

@app.route('/aggregated-price', methods=['GET'])
def get_aggregated_price():
    """집계된 가격 조회"""
    if not price_data_list:
        return jsonify({
            "status": "error",
            "message": "No price data available"
        }), 404
    
    # 최근 5개 가격의 평균
    recent_prices = [item['price'] for item in price_data_list[-5:]]
    aggregated_price = sum(recent_prices) / len(recent_prices)
    
    return jsonify({
        "aggregated_price": round(aggregated_price, 2),
        "data_points": len(recent_prices),
        "last_update": price_data_list[-1]["received_at"]
    })

@app.route('/price-history', methods=['GET'])
def get_price_history():
    """가격 히스토리 조회 (디버깅용)"""
    return jsonify({
        "total_data_points": len(price_data_list),
        "recent_data": price_data_list[-10:]  # 최근 10개만
    })

if __name__ == '__main__':
    print("🚀 Mock Aggregator starting on http://localhost:8081")
    print("📋 Available endpoints:")
    print("   GET  /health")
    print("   POST /submit-price") 
    print("   GET  /aggregated-price")
    print("   GET  /price-history")
    print()
    
    app.run(host='0.0.0.0', port=8081, debug=True)