import time
import json
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from config import Config
from database import DatabaseManager

class JSONChangeHandler(FileSystemEventHandler):
    def __init__(self, db):
        self.db = db
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
                
                # 检查内容是否实际发生变化
                if current_content != self.last_content:
                    self.last_content = current_content
                    
                    # 将新内容加入数据库
                    self.db.add_history_item(current_content)
                    
                    # 清理旧记录
                    self.db.cleanup_history()
                    
                    # 更新网页显示
                    # TODO: 实际项目中，这里应该触发网页更新
                    print(f"已更新历史记录")
            except Exception as e:
                print(f"处理JSON变更错误: {e}")

def main():
    db = DatabaseManager()
    
    # 监控JSON文件变化
    event_handler = JSONChangeHandler(db)
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
    db.close()

if __name__ == "__main__":
    main()