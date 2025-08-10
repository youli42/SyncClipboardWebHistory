import time
import json
import socketio
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from config import Config
from database import add_history_item_from_json

"""
​主线程​​：通过watchdog监控文件变化（同步阻塞）
​​子线程​​：专门处理通知队列（异步非阻塞）
"""

SOCKETIO_SERVER = 'http://localhost:5000'

class JSONChangeHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_content = self.get_current_content()
        self.sio = socketio.Client(reconnection=True, reconnection_attempts=5, reconnection_delay=1)
        self.connected = False
        self.notification_queue = []  # 通知队列
        self.notification_thread = None
        self.stop_notification = threading.Event()
        
        # 启动后台通知线程
        self.start_notification_thread()

    def start_notification_thread(self):
        """启动后台通知线程"""
        if self.notification_thread and self.notification_thread.is_alive():
            return
            
        self.notification_thread = threading.Thread(
            target=self.process_notification_queue,
            daemon=True
        )
        self.notification_thread.start()

    def process_notification_queue(self):
        """在独立的线程中处理通知：处理通知队列的后台线程"""
        while not self.stop_notification.is_set():
            if self.notification_queue:
                event_type = self.notification_queue.pop(0)
                self._send_notification(event_type)
            time.sleep(0.1)  # 避免CPU空转

    def _send_notification(self, event_type):
        """实际发送通知的方法"""
        try:
            if not self.connected:
                # 尝试连接（带超时）
                self.sio.connect(SOCKETIO_SERVER, wait_timeout=5) # 连接Socket.IO服务器
                self.connected = True
                print("Socket.IO 连接成功")
            
            if self.connected:
                self.sio.emit(event_type) # ⭐发送通知⭐
                print(f"已发送 {event_type} 通知")
        except Exception as e:
            
            # print(f"发送通知失败: {e}")

            self.connected = False
            # 短暂延迟后重试连接
            time.sleep(1)

    def get_current_content(self):
        try:
            with open(Config.SYNC_CLIPBOARD_JSON_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"读取JSON文件错误: {e}")
            return {}

    def on_modified(self, event): # 处理文件修改事件
        if event.src_path.endswith("SyncClipboard.json"): # 仅处理特定文件
            try:
                current_content = self.get_current_content()
                if current_content != self.last_content:
                    self.last_content = current_content

                    new_id = add_history_item_from_json(current_content)  # 将JSON内容添加到历史记录
                    print("已更新历史记录", new_id)
                    
                    # 将通知加入队列（非阻塞）
                    self.notification_queue.append('history_update')
                    
            except Exception as e:
                print(f"处理JSON变更错误: {e}")

    def stop(self):
        """停止后台线程"""
        self.stop_notification.set()
        if self.notification_thread and self.notification_thread.is_alive():
            self.notification_thread.join(timeout=2.0)
        if self.connected:
            self.sio.disconnect()

def main():
    event_handler = JSONChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, path='.', recursive=False)
    observer.start()
    try:
        print("监控服务已启动...")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        event_handler.stop()  # 确保停止后台线程
    observer.join()

if __name__ == "__main__":
    main()