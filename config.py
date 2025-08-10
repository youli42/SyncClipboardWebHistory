import os

class Config:
    # 基本路径配置
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
    # JSON 文件路径
    SYNC_CLIPBOARD_JSON_FILE = "SyncClipboard.json" # 同步文件名
    SYNC_CLIPBOARD_JSON_PATH = os.path.join(BASE_DIR, SYNC_CLIPBOARD_JSON_FILE) # 主同步文件路径
    

    # 数据库配置
    DB_PATH = os.path.join(BASE_DIR, "db", "clipboard_history.db")
    DB_LOG_ENABLED = True  # 是否启用数据库日志

    # 备份配置
    BACKUP_DIR = os.path.join(BASE_DIR, "backup")
    
    # 网页配置
    TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
    STATIC_DIR = os.path.join(BASE_DIR, "static")
    
    # 默认历史记录设置
    MAX_HISTORY_ITEMS = 500
    MAX_HISTORY_DAYS = 30
    MAX_STORAGE_MB = 100