FROM python:3.11-slim

# 設置工作目錄
WORKDIR /app

# 設置環境變量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# 複製依賴文件
COPY requirements.txt .

# 安裝依賴項
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir email-validator

# 複製應用程序代碼
COPY . .

# 暴露端口
EXPOSE 22000

# 啟動應用
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "22000"] 