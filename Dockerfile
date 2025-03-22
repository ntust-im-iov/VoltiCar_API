FROM python:3.11-slim

WORKDIR /app

# 複製依賴文件
COPY requirements.txt .

# 安裝依賴項
RUN pip install --no-cache-dir -r requirements.txt

# 複製應用程序代碼
COPY . .

# 暴露22000端口
EXPOSE 22000

# 啟動應用
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "22000", "--workers", "1"] 