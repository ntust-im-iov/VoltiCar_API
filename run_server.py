import uvicorn
import socket

# 獲取本機的內部IP地址
def get_local_ip():
    try:
        # 創建一個UDP套接字
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # 連接到一個外部服務器（不需要真正發送數據）
        s.connect(("8.8.8.8", 80))
        # 獲取分配給套接字的IP
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "無法獲取本機IP"

# 使用0.0.0.0綁定所有網絡介面
if __name__ == "__main__":
    host = "0.0.0.0"  # 綁定所有網絡介面
    port = 22000
    local_ip = get_local_ip()
    
    print(f"啟動API服務器於 {host}:{port}...")
    print(f"您的本機IP地址是: {local_ip}")
    print(f"您可以通過以下方式訪問API:")
    print(f"1. 本地訪問: http://localhost:{port}")
    print(f"2. 同一網絡內訪問: http://{local_ip}:{port}")
    print(f"3. 公網訪問: http://59.126.6.46:{port} (需確保路由器端口轉發已設置)")
    print(f"API文檔可在 /docs 路徑訪問")
    print("按 Ctrl+C 停止服務器")
    
    uvicorn.run("main:app", host=host, port=port) 