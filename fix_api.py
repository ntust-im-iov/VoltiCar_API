#!/usr/bin/env python
"""
Volticar API 修復腳本
解決：
1. 缺少email-validator依賴
2. MongoDB連接檢查語法問題
3. MongoDB索引重複鍵錯誤
"""
import os
import subprocess
import sys
import time
from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConnectionFailure, DuplicateKeyError, ServerSelectionTimeoutError

# 顯示標題
print("=" * 60)
print("Volticar API 修復工具")
print("=" * 60)

# 步驟1：安裝缺少的依賴
print("\n[步驟1] 安裝缺少的依賴項")
subprocess.run([sys.executable, "-m", "pip", "install", "email-validator"], check=True)
print("✓ 已安裝 email-validator")

# 步驟2：修復 MongoDB 連接檢查
print("\n[步驟2] 修復MongoDB連接檢查")
mongodb_file = "app/database/mongodb.py"

if os.path.exists(mongodb_file):
    with open(mongodb_file, "r", encoding="utf-8") as file:
        content = file.read()
    
    # 修復布爾檢查語法
    content = content.replace("if volticar_db:", "if volticar_db is not None:")
    content = content.replace("if client:", "if client is not None:")
    content = content.replace("if charge_station_db:", "if charge_station_db is not None:")
    
    with open(mongodb_file, "w", encoding="utf-8") as file:
        file.write(content)
    
    print(f"✓ 已修復 {mongodb_file} 中的MongoDB連接檢查")
else:
    print(f"✗ 找不到 {mongodb_file}")

print("\n[步驟3] 更新 requirements.txt")
with open("requirements.txt", "r", encoding="utf-8") as file:
    requirements = file.read()

if "email-validator" not in requirements:
    with open("requirements.txt", "a", encoding="utf-8") as file:
        file.write("email-validator>=2.0.0\n")
    print("✓ 已將 email-validator 添加到 requirements.txt")
else:
    print("✓ requirements.txt 已包含 email-validator")

print("\n[步驟4] 修復MongoDB索引重複鍵問題")
try:
    # 連接到MongoDB
    DATABASE_URL = os.getenv("DATABASE_URL", "mongodb://Volticar:REMOVED_PASSWORD@59.126.6.46:27017/?authSource=admin&ssl=false")
    print(f"嘗試連接到MongoDB: {DATABASE_URL.split('@')[-1]}")
    
    client = MongoClient(DATABASE_URL, serverSelectionTimeoutMS=5000)
    
    # 檢查連接
    client.admin.command('ping')
    print("✓ MongoDB連接成功!")
    
    # 獲取數據庫
    VOLTICAR_DB = os.getenv("VOLTICAR_DB", "Volticar")
    volticar_db = client[VOLTICAR_DB]
    
    # 處理用戶集合的索引問題
    users_collection = volticar_db["Users"]
    
    # 先刪除可能有問題的唯一索引
    print("   正在刪除現有索引...")
    for index_name in ["user_id_1", "email_1", "username_1", "phone_1", "google_id_1"]:
        try:
            users_collection.drop_index(index_name)
            print(f"   - 已刪除索引: {index_name}")
        except Exception as e:
            print(f"   - 刪除索引 {index_name} 時出錯: {e}")
    
    # 重新創建索引，確保使用sparse=True
    print("   重新創建索引，使用sparse=True...")
    try:
        users_collection.create_index([("user_id", ASCENDING)], unique=True, sparse=True)
        users_collection.create_index([("email", ASCENDING)], unique=True, sparse=True)
        users_collection.create_index([("username", ASCENDING)], unique=True, sparse=True)
        users_collection.create_index([("phone", ASCENDING)], unique=True, sparse=True)
        users_collection.create_index([("google_id", ASCENDING)], unique=True, sparse=True)
        print("✓ 已成功重新創建所有用戶索引")
    except Exception as e:
        print(f"✗ 創建索引時出錯: {e}")
except Exception as e:
    print(f"✗ 修復MongoDB索引時出錯: {e}")

print("\n" + "=" * 60)
print("修復完成！請重新啟動API服務：")
print("Windows: start_api.bat")
print("Docker: docker-compose down && docker-compose up -d")
print("=" * 60) 