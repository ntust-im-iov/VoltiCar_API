#!/usr/bin/env python
"""
MongoDB索引修復腳本
專門用於解決Volticar API的MongoDB索引重複鍵問題
增加複合索引和login_type欄位支持
"""
import os
import sys
import time
from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConnectionFailure, DuplicateKeyError, ServerSelectionTimeoutError

print("=" * 60)
print("MongoDB索引修復工具 (複合索引版)")
print("=" * 60)

# 連接到MongoDB
DATABASE_URL = os.getenv("DATABASE_URL", "mongodb://Volticar:RJW1128@59.126.6.46:27017/?authSource=admin&ssl=false")
VOLTICAR_DB = os.getenv("VOLTICAR_DB", "Volticar")

print(f"\n[步驟1] 連接到MongoDB: {DATABASE_URL.split('@')[-1]}")
try:
    client = MongoClient(DATABASE_URL, serverSelectionTimeoutMS=5000)
    
    # 執行簡單的ping命令檢查連接
    client.admin.command('ping')
    print(f"✓ 連接成功! 伺服器版本: {client.server_info()['version']}")
    
    # 獲取數據庫和集合
    db = client[VOLTICAR_DB]
    users_collection = db["Users"]
    
    print(f"\n[步驟2] 檢查Users集合中的文檔數量")
    doc_count = users_collection.count_documents({})
    print(f"✓ 總共發現 {doc_count} 個文檔")
    
    print("\n[步驟3] 添加新的login_type欄位")
    # 計算沒有login_type欄位的文檔數
    missing_login_type = users_collection.count_documents({"login_type": {"$exists": False}})
    print(f"發現 {missing_login_type} 個文檔沒有login_type欄位")
    
    if missing_login_type > 0:
        # 為有google_id的用戶設置login_type為'google'
        result1 = users_collection.update_many(
            {"login_type": {"$exists": False}, "google_id": {"$ne": None, "$exists": True}},
            {"$set": {"login_type": "google"}}
        )
        print(f"✓ 已為 {result1.modified_count} 個Google用戶添加login_type欄位")
        
        # 為其餘用戶設置login_type為'password'
        result2 = users_collection.update_many(
            {"login_type": {"$exists": False}},
            {"$set": {"login_type": "password"}}
        )
        print(f"✓ 已為 {result2.modified_count} 個一般用戶添加login_type欄位")
    
    print("\n[步驟4] 檢查並刪除現有索引")
    indexes = users_collection.index_information()
    print(f"發現 {len(indexes)} 個索引:")
    for index_name, index_info in indexes.items():
        if index_name != "_id_":  # 不刪除主索引
            print(f"  - 刪除索引: {index_name}")
            users_collection.drop_index(index_name)
    print("✓ 已刪除所有非主索引")
    
    print("\n[步驟5] 檢查並修改google_id欄位")
    # 對於login_type='password'的用戶，完全移除google_id欄位
    password_users = users_collection.count_documents({
        "login_type": "password",
        "google_id": {"$exists": True}
    })
    
    if password_users > 0:
        users_collection.update_many(
            {"login_type": "password"},
            {"$unset": {"google_id": ""}}
        )
        print(f"✓ 已從 {password_users} 個一般用戶移除google_id欄位")
    
    # 確保所有google用戶有有效的google_id
    invalid_google_ids = users_collection.count_documents({
        "login_type": "google",
        "$or": [
            {"google_id": None},
            {"google_id": ""},
            {"google_id": {"$exists": False}}
        ]
    })
    
    if invalid_google_ids > 0:
        print(f"警告: 發現 {invalid_google_ids} 個Google用戶的google_id無效")
        # 將這些用戶改為password類型
        users_collection.update_many(
            {
                "login_type": "google",
                "$or": [
                    {"google_id": None},
                    {"google_id": ""},
                    {"google_id": {"$exists": False}}
                ]
            },
            {"$set": {"login_type": "password"}, "$unset": {"google_id": ""}}
        )
        print(f"✓ 已將這些用戶改為一般用戶類型並移除無效的google_id欄位")
    
    print("\n[步驟6] 創建新的索引，包括複合索引")
    # 主要欄位索引
    try:
        print("  創建user_id索引")
        users_collection.create_index([("user_id", ASCENDING)], unique=True, sparse=True)
        print("  ✓ 已成功創建索引: user_id")
        
        print("  創建email索引")
        users_collection.create_index([("email", ASCENDING)], unique=True, sparse=True)
        print("  ✓ 已成功創建索引: email")
        
        print("  創建username索引")
        users_collection.create_index([("username", ASCENDING)], unique=True, sparse=True)
        print("  ✓ 已成功創建索引: username")
        
        print("  創建phone索引")
        users_collection.create_index([("phone", ASCENDING)], unique=True, sparse=True)
        print("  ✓ 已成功創建索引: phone")
        
        # 創建google_id和login_type的複合索引
        print("  創建google_id和login_type的複合索引")
        users_collection.create_index(
            [("google_id", ASCENDING), ("login_type", ASCENDING)],
            unique=True,
            sparse=True
        )
        print("  ✓ 已成功創建複合索引: google_id + login_type")
        
    except Exception as e:
        print(f"  ✗ 創建索引時出錯: {str(e)}")
    
    print("\n[步驟7] 驗證索引創建結果")
    new_indexes = users_collection.index_information()
    print(f"✓ 成功創建 {len(new_indexes)-1} 個索引:")
    for index_name, index_info in new_indexes.items():
        if index_name != "_id_":
            print(f"  - {index_name}: {index_info}")
            
    print("\n✓ MongoDB索引修復完成!")
    
except Exception as e:
    print(f"✗ 執行過程中發生錯誤: {str(e)}")

print("\n" + "=" * 60)
print("請重新啟動API服務:")
print("Windows: start_api.bat")
print("Docker: docker-compose down && docker-compose up -d")
print("=" * 60) 