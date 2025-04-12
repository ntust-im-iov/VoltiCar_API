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

# 安裝系統級依賴項 (用於編譯套件)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 升級 pip 和相關建置工具
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# 安裝依賴項
RUN pip install --no-cache-dir -r requirements.txt

# 複製應用程序代碼
COPY . .

# 暴露端口
EXPOSE 22000

# 啟動應用
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "22000"]
