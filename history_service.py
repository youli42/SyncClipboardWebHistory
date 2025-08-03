import time
import json
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from config import Config
from database import DatabaseManager

class JSONChangeHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_content = self.get_current_content()
    
    def get_current_content(self):
        try:
            with open(Config.SYNC_CLIPBOARD_JSON, 'r', encoding='utf-8') as f:
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
                    # 每次变更都新建一个数据库连接
                    db = DatabaseManager()
                    db.add_history_item(current_content)
                    db.cleanup_history()
                    db.close()
                    print(f"已更新历史记录")
            except Exception as e:
                print(f"处理JSON变更错误: {e}")

def main():
    # 不需要提前创建 db
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