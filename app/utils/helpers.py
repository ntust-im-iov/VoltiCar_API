from bson import ObjectId
import json
from typing import Any, Dict, List

# 將MongoDB數據轉換為可序列化的格式
def handle_mongo_data(data):
    """遞歸處理MongoDB數據，將ObjectId轉換為字符串"""
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, ObjectId):
                data[key] = str(value)
            elif isinstance(value, (dict, list)):
                data[key] = handle_mongo_data(value)
    elif isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, ObjectId):
                data[i] = str(item)
            elif isinstance(item, (dict, list)):
                data[i] = handle_mongo_data(item)
    return data

# 用於處理ObjectId的JSON編碼器
class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return super(JSONEncoder, self).default(obj) 