#!/usr/bin/env python
"""
MongoDB索引修復腳本
專門用於解決Volticar API的MongoDB索引重複鍵問題
使用user_id作為臨時google_id，直到用戶綁定Google帳號
"""
import os
import sys
import time
from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConnectionFailure, DuplicateKeyError, ServerSelectionTimeoutError

print("=" * 60)
print("MongoDB索引修復工具")
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
    
    # 計算沒有google_id欄位的文檔數
    missing_google_id = users_collection.count_documents({"google_id": {"$exists": False}})
    print(f"發現 {missing_google_id} 個文檔沒有google_id欄位")
    
    # 遍歷所有用戶並確保他們有正確的欄位
    print("\n[步驟3.1] 更新所有用戶的login_type和google_id欄位")
    
    # 先將所有沒有login_type的用戶設為'normal'
    if missing_login_type > 0:
        result1 = users_collection.update_many(
            {"login_type": {"$exists": False}},
            {"$set": {"login_type": "normal"}}
        )
        print(f"✓ 已為 {result1.modified_count} 個用戶添加login_type=normal欄位")
    
    # 為所有沒有google_id的用戶設置google_id為user_id
    if missing_google_id > 0:
        # 直接方式：使用update_many
        result2 = users_collection.update_many(
            {"google_id": {"$exists": False}},
            {"$set": {"google_id": ""}}  # 先設為空字符串
        )
        print(f"✓ 已為 {result2.modified_count} 個用戶創建google_id欄位")
        
        # 遍歷所有用戶並更新google_id
        cursor = users_collection.find({"google_id": ""})
        update_count = 0
        for user in cursor:
            if "user_id" in user:
                users_collection.update_one(
                    {"_id": user["_id"]},
                    {"$set": {"google_id": user["user_id"]}}
                )
                update_count += 1
        
        print(f"✓ 已將 {update_count} 個用戶的google_id設置為user_id")
    
    # 確保所有用戶都有正確的google_id和login_type
    print("\n[步驟3.2] 驗證所有欄位更新")
    still_missing_google_id = users_collection.count_documents({"google_id": {"$exists": False}})
    still_missing_login_type = users_collection.count_documents({"login_type": {"$exists": False}})
    
    print(f"仍有 {still_missing_google_id} 個用戶沒有google_id欄位")
    print(f"仍有 {still_missing_login_type} 個用戶沒有login_type欄位")
    
    print("\n[步驟4] 檢查並刪除現有索引")
    indexes = users_collection.index_information()
    print(f"發現 {len(indexes)} 個索引:")
    for index_name, index_info in indexes.items():
        if index_name != "_id_":  # 不刪除主索引
            print(f"  - 刪除索引: {index_name}")
            users_collection.drop_index(index_name)
    print("✓ 已刪除所有非主索引")
    
    print("\n[步驟5] 創建新的索引")
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
        
        print("  創建google_id索引")
        users_collection.create_index([("google_id", ASCENDING)], unique=True, sparse=True)
        print("  ✓ 已成功創建索引: google_id")
        
        print("  創建login_type索引")
        users_collection.create_index([("login_type", ASCENDING)])
        print("  ✓ 已成功創建索引: login_type")
        
    except Exception as e:
        print(f"  ✗ 創建索引時出錯: {str(e)}")
    
    print("\n[步驟6] 驗證索引創建結果")
    new_indexes = users_collection.index_information()
    print(f"✓ 成功創建 {len(new_indexes)-1} 個索引:")
    for index_name, index_info in new_indexes.items():
        if index_name != "_id_":
            print(f"  - {index_name}: {index_info}")
    
    # 驗證一個用戶記錄
    print("\n[步驟7] 驗證用戶記錄")
    sample_user = users_collection.find_one()
    if sample_user:
        print("用戶記錄示例:")
        for key, value in sample_user.items():
            print(f"  - {key}: {value}")
            
    print("\n✓ MongoDB索引修復完成!")
    
except Exception as e:
    print(f"✗ 執行過程中發生錯誤: {str(e)}")

print("\n" + "=" * 60)
print("請重新啟動API服務:")
print("Windows: start_api.bat")
print("Docker: docker-compose down && docker-compose up -d")
print("=" * 60) 