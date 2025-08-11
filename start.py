import threading
import time
import signal
import sys
import web_server
import history_service
import database

# 全局退出标志
exit_event = threading.Event()

def start_monitor():
    """启动剪贴板监控服务（支持优雅退出）"""
    while not exit_event.is_set():
        # 替换为您的实际监控逻辑
        history_service.main()
        time.sleep(0.1)  # 避免CPU占用过高

def start_web():
    """启动 Web 服务（支持优雅退出）"""
    # 关键修复：禁用重载器
    # web_server.socketio.run(web_server.app, port=5000, debug=True)  # 用 socketio.run 启动
    web_server.socketio.run(web_server.app, port=5000, debug=True, use_reloader=False)  # 禁用重载器

def signal_handler(sig, frame):
    """处理中断信号"""
    print("\n接收到退出信号，正在优雅关闭服务...")
    exit_event.set()  # 设置退出标志
    
    # 等待服务关闭（最多1秒）
    print("等待服务线程结束...")
    monitor_thread.join(timeout=5.0)
    web_thread.join(timeout=1.0)
    
    # 强制退出（如果线程未正常结束）
    if monitor_thread.is_alive() or web_thread.is_alive():
        print("服务线程未及时结束，强制退出")
        sys.exit(1)
    else:
        print("所有服务已安全关闭")
        sys.exit(0)

if __name__ == "__main__":
    # 初始化数据库
    db_engine = database.init_db()
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 创建线程
    monitor_thread = threading.Thread(target=start_monitor, name="MonitorThread", daemon=True)
    web_thread = threading.Thread(target=start_web, name="WebThread", daemon=True)

    # 启动线程
    monitor_thread.start()
    web_thread.start()
    print("服务已启动，按 Ctrl+C 退出")

    try:
        # 主线程保持运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)
