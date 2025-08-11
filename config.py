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
    BACKUP_DIR_FOLDER = "backup"  # 当前文件夹下，备份文件夹名称

    BACKUP_DIR = os.path.join(BASE_DIR, BACKUP_DIR_FOLDER)
    
    # 网页配置
    TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
    STATIC_DIR = os.path.join(BASE_DIR, "static")
    
    # 历史文件删除配置
    MAX_FOLDER_SIZE = "1G"  # 支持格式: "100MB", "2GB", "512KB", "1024B"
    CHECK_INTERVAL = 60  # 检查间隔（秒）
    FOLDER_TO_MONITOR = os.path.join(BASE_DIR, BACKUP_DIR_FOLDER)  # 替换为要监控的文件夹路径，一般和备份文件夹相同


if __name__ == "__main__":
    # 测试配置
    print("基础目录:", Config.BASE_DIR)
    print("配置文件路径:", Config.SYNC_CLIPBOARD_JSON_PATH)
    print("数据库路径:", Config.DB_PATH)
    print("备份目录:", Config.BACKUP_DIR)
    print("模板目录:", Config.TEMPLATES_DIR)
    print("静态文件目录:", Config.STATIC_DIR)
    print("监控文件夹:", Config.FOLDER_TO_MONITOR)
    print("最大文件夹大小:", Config.MAX_FOLDER_SIZE)
    print("检查间隔:", Config.CHECK_INTERVAL, "秒")
    print("配置加载成功")