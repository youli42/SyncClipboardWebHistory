import time
import json
import socketio
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from config import Config
from database import DatabaseManager

SOCKETIO_SERVER = 'http://localhost:5000'

class JSONChangeHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_content = self.get_current_content()
        self.sio = socketio.Client()
        self.connected = False  # 新增：连接状态

    def connect_socketio(self):
        if not self.connected:
            try:
                self.sio.connect(SOCKETIO_SERVER)
                self.connected = True
            except Exception as e:
                print(f"SocketIO 连接失败: {e}")
                self.connected = False

    def get_current_content(self):
        try:
            with open(Config.SYNC_CLIPBOARD_JSON_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"读取JSON文件错误: {e}")
            return {}

    def on_modified(self, event):
        if event.src_path.endswith("SyncClipboard.json"):
            try:
                current_content = self.get_current_content()
                if current_content != self.last_content:
                    self.last_content = current_content
                    db = DatabaseManager()
                    db.add_history_item(current_content)
                    db.cleanup_history()
                    db.close()
                    print(f"已更新历史记录")
                    # 只有在需要通知时才尝试连接
                    self.connect_socketio()
                    if self.connected:
                        self.sio.emit('history_update')
                    else:
                        print("SocketIO 未连接，无法通知 Web 服务")
            except Exception as e:
                print(f"处理JSON变更错误: {e}")

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
    observer.join()

if __name__ == "__main__":
    main()