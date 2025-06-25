#!/bin/bash

echo "Testing Oracle Node API..."

# Health check
echo -e "\n1. Health Check:"
curl -s http://localhost:8080/health

# Get current price
echo -e "\n\n2. Current Price:"
curl -s http://localhost:8080/price | jq .

# Get all prices
echo -e "\n3. All Prices (first 3):"
curl -s http://localhost:8080/prices | jq '.prices[:3]'

echo -e "\n4. Price Count:"
curl -s http://localhost:8080/prices | jq '.count'