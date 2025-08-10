import sqlite3
from datetime import datetime, timedelta
import random
import os

def init_test_database(db_name='clipboard_history.db'):
    """初始化测试数据库，创建必要的表"""
    conn = sqlite3.connect(db_name)
    c = conn.cursor()
    
    # 创建历史记录表（如果不存在）
    c.execute('''
    CREATE TABLE IF NOT EXISTS clipboard_history
    (id INTEGER PRIMARY KEY AUTOINCREMENT,
     content TEXT NOT NULL,
     file_name TEXT,
     type TEXT NOT NULL,
     source TEXT,
     timestamp DATETIME NOT NULL,
     is_favorite INTEGER DEFAULT 0,
     favorite_folder TEXT)
    ''')
    
    # 创建设置表（如果不存在）
    c.execute('''
    CREATE TABLE IF NOT EXISTS settings
    (id INTEGER PRIMARY KEY AUTOINCREMENT,
     key TEXT UNIQUE NOT NULL,
     value TEXT NOT NULL)
    ''')
    
    # 插入默认设置（如果不存在）
    default_settings = [
        ('max_history_items', '1000'),
        ('max_storage_days', '30'),
        ('max_storage_size', '1024')
    ]
    
    for key, value in default_settings:
        c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (key, value))
    
    conn.commit()
    conn.close()

def generate_test_data(num_records=20, db_name='clipboard_history.db'):
    """生成测试数据并插入数据库"""
    # 确保数据库已初始化
    init_test_database(db_name)
    
    conn = sqlite3.connect(db_name)
    c = conn.cursor()
    
    # 测试文本内容
    test_texts = [
        "这是一段测试文本内容",
        "SyncClipboard是一个很棒的剪贴板同步工具",
        "https://github.com/Jeric-X/SyncClipboard",
        "Python 3.11 是最新的Python版本",
        "Flask是一个轻量级的Web框架",
        "今天的天气真好，适合出去走走",
        "学习编程是一个持续积累的过程",
        "数据库设计很重要",
        "1234567890 这是一串数字",
        "!@#$%^&*() 这是一些特殊字符"
    ]
    
    # 测试文件名
    test_files = [
        "document.pdf",
        "image.png",
        "archive.zip",
        "data.csv",
        "presentation.pptx",
        "notes.txt",
        "photo.jpg",
        "video.mp4",
        "code.py",
        "music.mp3"
    ]
    
    # 测试来源
    sources = ["电脑", "手机", "平板", "Nova11", "Web", ""]
    
    # 生成记录
    for i in range(num_records):
        # 随机选择记录类型
        record_type = random.choice(["Text", "Image", "File"])
        
        # 根据类型生成内容
        if record_type == "Text":
            content = random.choice(test_texts)
            file_name = ""
        elif record_type == "Image":
            content = f"image_hash_{random.randint(1000, 9999)}"
            file_name = random.choice([f"img_{i}.png", f"photo_{i}.jpg", f"pic_{i}.gif"])
        else:  # File
            content = f"file_hash_{random.randint(1000, 9999)}"
            file_name = random.choice(test_files)
        
        # 随机选择来源
        source = random.choice(sources)
        
        # 随机生成时间（过去7天内）
        days_ago = random.randint(0, 7)
        hours_ago = random.randint(0, 23)
        minutes_ago = random.randint(0, 59)
        
        timestamp = datetime.now() - timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago)
        timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
        
        # 随机标记一些为收藏
        is_favorite = 1 if random.random() < 0.2 else 0
        
        # 随机分配收藏夹（如果是收藏的）
        favorite_folder = ""
        if is_favorite:
            favorite_folder = random.choice(["工作", "个人", "重要", "临时/待处理"])
        
        # 插入数据库
        c.execute('''
        INSERT INTO clipboard_history 
        (content, file_name, type, source, timestamp, is_favorite, favorite_folder)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (content, file_name, record_type, source, timestamp_str, is_favorite, favorite_folder))
    
    conn.commit()
    conn.close()
    print(f"成功生成 {num_records} 条测试数据")

def clear_test_data(db_name='clipboard_history.db'):
    """清空测试数据"""
    if not os.path.exists(db_name):
        print("数据库文件不存在")
        return
        
    conn = sqlite3.connect(db_name)
    c = conn.cursor()
    
    c.execute('DELETE FROM clipboard_history')
    conn.commit()
    conn.close()
    print("已清空所有测试数据")

if __name__ == "__main__":
    # 初始化数据库并生成30条测试数据
    init_test_database()
    generate_test_data(30)
    # 如果需要清空数据，可以调用：
    # clear_test_data()
    