import os
import requests
from pymongo import MongoClient

# Test MongoDB connection
print("Testing MongoDB connection...")
try:
    client = MongoClient("mongodb://Volticar:REMOVED_PASSWORD@59.126.6.46:27017/?authSource=admin")
    db_names = client.list_database_names()
    print(f"Successfully connected to MongoDB. Available databases: {db_names}")
except Exception as e:
    print(f"Failed to connect to MongoDB: {e}")

# Test local API connection
print("\nTesting local API connection...")
try:
    response = requests.get("http://localhost:22000/health")
    print(f"API response: {response.status_code} - {response.text}")
except Exception as e:
    print(f"Failed to connect to local API: {e}")

print("\nTesting connection from container to host network...")
try:
    response = requests.get("http://host.docker.internal:22000/health")
    print(f"API response via host.docker.internal: {response.status_code} - {response.text}")
except Exception as e:
    print(f"Failed to connect via host.docker.internal: {e}")

# Test external IP connection
print("\nTesting external IP connection...")
try:
    response = requests.get("http://59.126.6.46:22000/health")
    print(f"External API response: {response.status_code} - {response.text}")
except Exception as e:
    print(f"Failed to connect to external IP: {e}")

print("\nNetwork connectivity tests completed.") 