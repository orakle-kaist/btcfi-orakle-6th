#!/usr/bin/env python3
import requests
import json
import traceback

url = "http://localhost:8081/api/v1/next_step"
data = {"setup_uuid": "60f1041f-1a8f-4e17-8181-44208f11b71c"}

try:
    response = requests.post(url, json=data)
    print(f"Response status: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"Error: {e}")
    traceback.print_exc()