#!/usr/bin/env python
"""
MongoDB索引修復腳本
專門用於解決Volticar API的MongoDB索引重複鍵問題
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
    
    print("\n[步驟3] 檢查並刪除現有索引")
    indexes = users_collection.index_information()
    print(f"發現 {len(indexes)} 個索引:")
    for index_name, index_info in indexes.items():
        if index_name != "_id_":  # 不刪除主索引
            print(f"  - 刪除索引: {index_name}")
            users_collection.drop_index(index_name)
    print("✓ 已刪除所有非主索引")
    
    print("\n[步驟4] 檢查並處理重複的null值文檔")
    
    # 檢查重要字段的null值
    fields_to_check = ["user_id", "email", "username", "phone", "google_id"]
    for field in fields_to_check:
        null_count = users_collection.count_documents({field: None})
        print(f"  - {field}: {null_count} 個null值")
        
        if null_count > 1:
            print(f"    正在處理重複的{field}為null的文檔...")
            # 查找具有null值的文檔
            null_docs = list(users_collection.find({field: None}))
            
            # 保留第一個文檔，為其他文檔完全移除該欄位
            for i, doc in enumerate(null_docs[1:], 1):
                print(f"    更新文檔 {doc['_id']} 的 {field} 字段 (完全移除)")
                users_collection.update_one(
                    {"_id": doc["_id"]},
                    {"$unset": {field: ""}}  # 完全移除該字段
                )
            print(f"    ✓ 已處理 {len(null_docs)-1} 個重複的{field}為null的文檔")
    
    # 特別處理google_id字段，檢查是否有空字符串值
    empty_google_id_count = users_collection.count_documents({"google_id": ""})
    if empty_google_id_count > 0:
        print(f"  - 發現 {empty_google_id_count} 個google_id為空字符串的文檔")
        # 將空字符串google_id完全移除
        users_collection.update_many(
            {"google_id": ""},
            {"$unset": {"google_id": ""}}
        )
        print(f"    ✓ 已移除 {empty_google_id_count} 個空字符串google_id")
    
    print("\n[步驟5] 重新創建索引，使用sparse=True選項")
    
    # 為每個字段創建索引
    for field in fields_to_check:
        try:
            print(f"  創建索引: {field}")
            users_collection.create_index([(field, ASCENDING)], unique=True, sparse=True)
            print(f"  ✓ 已成功創建索引: {field}")
        except Exception as e:
            print(f"  ✗ 創建索引 {field} 時出錯: {str(e)}")
    
    print("\n[步驟6] 驗證索引創建結果")
    new_indexes = users_collection.index_information()
    print(f"✓ 成功創建 {len(new_indexes)-1} 個索引:")
    for index_name, index_info in new_indexes.items():
        if index_name != "_id_":
            print(f"  - {index_name}: {index_info}")
            
    print("\n[步驟7] 修復google_id索引特殊問題")
    # 檢查是否還有文檔具有google_id: null
    null_google_ids = list(users_collection.find({"google_id": None}))
    if len(null_google_ids) > 0:
        print(f"  仍有 {len(null_google_ids)} 個文檔的google_id為null，嘗試更徹底的修復...")
        
        # 更徹底的修復：完全移除google_id字段
        for doc in null_google_ids:
            users_collection.update_one(
                {"_id": doc["_id"]},
                {"$unset": {"google_id": ""}}
            )
        
        # 重新創建google_id索引
        try:
            users_collection.drop_index("google_id_1")
            users_collection.create_index([("google_id", ASCENDING)], unique=True, sparse=True)
            print("  ✓ google_id索引已重新創建")
        except Exception as e:
            print(f"  ✗ 重新創建google_id索引時出錯: {str(e)}")
    else:
        print("  ✓ google_id索引問題已解決")
            
    print("\n✓ MongoDB索引修復完成!")
    
except Exception as e:
    print(f"✗ 執行過程中發生錯誤: {str(e)}")

print("\n" + "=" * 60)
print("請重新啟動API服務:")
print("Windows: start_api.bat")
print("Docker: docker-compose down && docker-compose up -d")
print("=" * 60) 