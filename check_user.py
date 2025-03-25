#!/usr/bin/env python
"""
檢查MongoDB用戶記錄，確認google_id欄位是否存在
"""
import os
from pymongo import MongoClient

# 連接到MongoDB
DATABASE_URL = os.getenv("DATABASE_URL", "mongodb://Volticar:RJW1128@59.126.6.46:27017/?authSource=admin&ssl=false")
VOLTICAR_DB = os.getenv("VOLTICAR_DB", "Volticar")

try:
    client = MongoClient(DATABASE_URL, serverSelectionTimeoutMS=5000)
    
    # 執行簡單的ping命令檢查連接
    client.admin.command('ping')
    print(f"連接成功! 伺服器版本: {client.server_info()['version']}")
    
    # 獲取數據庫和集合
    db = client[VOLTICAR_DB]
    users_collection = db["Users"]
    
    # 獲取一個用戶記錄
    user = users_collection.find_one()
    
    if user:
        print("\n用戶記錄內容:")
        for key, value in user.items():
            print(f"{key}: {value}")
        
        # 特別檢查 google_id 欄位
        if "google_id" in user:
            print(f"\ngoogle_id欄位存在，值為: {user['google_id']}")
        else:
            print("\ngoogle_id欄位不存在")
    else:
        print("沒有找到用戶記錄")
    
except Exception as e:
    print(f"錯誤: {str(e)}") 