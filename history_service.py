import time
import json
import socketio
import threading
import os
import re
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

###################
## 监控文件夹大小并删除最旧的文件
###################



def parse_size(size_str):
    """
    将带单位的大小字符串转换为字节数
    支持的单位: B, KB, MB, GB (不区分大小写)
    示例: "1GB" -> 1073741824, "500MB" -> 524288000
    """
    # 正则表达式匹配数字和单位
    match = re.match(r'^(\d+(\.\d+)?)\s*([BKMG]B?)$', size_str.strip(), re.IGNORECASE)
    if not match:
        raise ValueError(f"无效的大小格式: {size_str}。请使用类似 '1GB', '500MB' 的格式")
    
    size = float(match.group(1))
    unit = match.group(3).upper()
    
    # 单位转换为字节
    units = {
        'B': 1,
        'KB': 1024,
        'MB': 1024 **2,
        'GB': 1024** 3,
        'G': 1024** 3
    }
    
    return int(size * units[unit])

def get_folder_size(folder_path):
    """计算文件夹的总大小（字节）"""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(folder_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            # 只计算文件大小，忽略符号链接
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)
    return total_size

def get_oldest_file(folder_path):
    """获取文件夹中最旧的文件路径"""
    files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) 
             if os.path.isfile(os.path.join(folder_path, f))]
    if not files:
        return None
    # 按创建时间排序，返回最旧的文件
    return min(files, key=os.path.getctime)

def delete_oldest_files(folder_path, max_size):
    """删除最旧的文件，直到文件夹大小低于max_size"""
    current_size = get_folder_size(folder_path)
    
    if current_size <= max_size:
        return False  # 不需要删除文件
    
    print(f"文件夹大小 {format_size(current_size)} 超过阈值 {format_size(max_size)}，开始清理...")
    
    while current_size > max_size:
        oldest_file = get_oldest_file(folder_path)
        if not oldest_file:
            print("文件夹已空，但仍超过大小限制")
            break
            
        file_size = os.path.getsize(oldest_file)
        try:
            os.remove(oldest_file)
            print(f"已删除文件: {oldest_file} (大小: {format_size(file_size)})")
            current_size -= file_size
        except Exception as e:
            print(f"删除文件 {oldest_file} 失败: {e}")
            break
    
    return True

def format_size(size_bytes):
    """将字节数格式化为带单位的易读字符串"""
    units = ['B', 'KB', 'MB', 'GB']
    unit_index = 0
    size = size_bytes
    
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    
    return f"{size:.2f} {units[unit_index]}"

def monitor_backup_folder(folder_path, max_size_str, check_interval=60):
    """
    监控文件夹大小并删除最旧的文件，直到大小低于指定阈值
    """
    if not os.path.exists(folder_path):
        print(f"错误: 文件夹 {folder_path} 不存在")
        return
        
    try:
        max_size = parse_size(max_size_str)
    except ValueError as e:
        print(f"配置错误: {e}")
        return
        
    print(f"开始监控文件夹: {folder_path}")
    print(f"最大允许大小: {max_size_str} ({format_size(max_size)})")
    print(f"检查间隔: {check_interval} 秒")
    
    try:
        while True:
            delete_oldest_files(folder_path, max_size)
            time.sleep(check_interval)
    except KeyboardInterrupt:
        print("\n监控已停止")

if __name__ == "monitor folder":
    # 配置参数 - 现在可以直接使用带单位的字符串
    FOLDER_TO_MONITOR = "/path/to/your/folder"  # 替换为要监控的文件夹路径
    MAX_FOLDER_SIZE = "1GB"  # 支持格式: "100MB", "2GB", "512KB", "1024B"
    CHECK_INTERVAL = 60  # 检查间隔（秒）
    
    # 启动监控
    monitor_backup_folder(FOLDER_TO_MONITOR, MAX_FOLDER_SIZE, CHECK_INTERVAL)


if __name__ == "__main__":
    # main()
    
    # 文件夹大小限制
    monitor_backup_folder(Config.FOLDER_TO_MONITOR, Config.MAX_FOLDER_SIZE, Config.CHECK_INTERVAL)