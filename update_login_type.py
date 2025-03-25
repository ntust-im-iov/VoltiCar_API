#!/usr/bin/env python
"""
更新資料庫中的 login_type 欄位，將 "password" 改為 "normal"
"""
import os
from pymongo import MongoClient

# 連接到MongoDB
DATABASE_URL = os.getenv("DATABASE_URL", "mongodb://Volticar:REMOVED_PASSWORD@59.126.6.46:27017/?authSource=admin&ssl=false")
VOLTICAR_DB = os.getenv("VOLTICAR_DB", "Volticar")

print("連接到MongoDB...")
try:
    client = MongoClient(DATABASE_URL, serverSelectionTimeoutMS=5000)
    
    # 執行簡單的ping命令檢查連接
    client.admin.command('ping')
    print(f"連接成功! 伺服器版本: {client.server_info()['version']}")
    
    # 獲取數據庫和集合
    db = client[VOLTICAR_DB]
    users_collection = db["Users"]
    
    # 查找並更新所有 login_type="password" 的用戶
    password_users = users_collection.count_documents({"login_type": "password"})
    print(f"找到 {password_users} 個 login_type='password' 的用戶")
    
    if password_users > 0:
        result = users_collection.update_many(
            {"login_type": "password"},
            {"$set": {"login_type": "normal"}}
        )
        print(f"已成功更新 {result.modified_count} 個用戶")
    
    # 驗證更新結果
    remaining = users_collection.count_documents({"login_type": "password"})
    normal_users = users_collection.count_documents({"login_type": "normal"})
    print(f"更新後: 還有 {remaining} 個 'password' 用戶，{normal_users} 個 'normal' 用戶")
    
    # 查看一個用戶記錄作為範例
    user = users_collection.find_one({"login_type": "normal"})
    if user:
        print("\n用戶記錄範例:")
        for key, value in user.items():
            print(f"  - {key}: {value}")
    
    print("\n更新完成!")
    
except Exception as e:
    print(f"錯誤: {str(e)}") 