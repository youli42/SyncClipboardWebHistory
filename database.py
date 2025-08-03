import sqlite3
import os
from config import Config
import shutil
import uuid
import hashlib
import json
from datetime import datetime

class DatabaseManager:
    def __init__(self):
        os.makedirs(os.path.dirname(Config.DB_PATH), exist_ok=True)
        os.makedirs(Config.BACKUP_DIR, exist_ok=True)
        self.conn = sqlite3.connect(Config.DB_PATH)
        self.create_tables()

        # 配置页面功能
        cursor = self.conn.cursor()  # 修复：先获取游标
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        self.conn.commit()
        
    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS clipboard_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            content TEXT,
            file_path TEXT,
            from_source TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_starred BOOLEAN DEFAULT 0
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS collections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            parent_id INTEGER DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS collection_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collection_id INTEGER NOT NULL,
            history_id INTEGER NOT NULL,
            FOREIGN KEY(collection_id) REFERENCES collections(id),
            FOREIGN KEY(history_id) REFERENCES clipboard_history(id)
        )
        ''')
        
        self.conn.commit()
    
    def add_history_item(self, data):
        """添加新的剪贴板历史记录"""
        cursor = self.conn.cursor()
        
        # 提取数据
        item_type = data.get("Type", "")
        file_name = data.get("File", "")
        clipboard = data.get("Clipboard", "")
        from_source = data.get("From", "")
        tags = data.get("Tag", "")
        
        # 备份文件（如果是图片或文件）
        backup_path = None
        if item_type in ["Image", "File"]:
            original_path = os.path.join("file", clipboard)
            if os.path.exists(original_path):
                # 生成唯一的备份文件名
                ext = os.path.splitext(file_name)[1] if file_name else ""
                unique_name = f"{uuid.uuid4().hex}{ext}"
                backup_path = os.path.join(Config.BACKUP_DIR, unique_name)
                
                # 复制文件到备份目录
                shutil.copy2(original_path, backup_path)
        
        # 准备要插入的内容
        content = file_name if item_type != "Text" else clipboard
        
        cursor.execute('''
        INSERT INTO clipboard_history 
        (type, content, file_path, from_source, timestamp) 
        VALUES (?, ?, ?, ?, datetime('now'))
        ''', (item_type, content, backup_path, from_source))
        
        self.conn.commit()
        return cursor.lastrowid
    
    def get_history(self, limit=None, offset=0, filters=None):
        """获取历史记录"""
        cursor = self.conn.cursor()
        query = "SELECT * FROM clipboard_history"
        params = []
        
        # 构建过滤条件
        conditions = []
        if filters:
            if "type" in filters and filters["type"]:
                conditions.append("type = ?")
                params.append(filters["type"])
            if "source" in filters and filters["source"]:
                conditions.append("from_source = ?")
                params.append(filters["source"])
            if "start_date" in filters and filters["start_date"]:
                conditions.append("DATE(timestamp) >= ?")
                params.append(filters["start_date"])
            if "end_date" in filters and filters["end_date"]:
                conditions.append("DATE(timestamp) <= ?")
                params.append(filters["end_date"])
            if "starred" in filters and filters["starred"]:
                conditions.append("is_starred = 1")
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        # 排序
        query += " ORDER BY timestamp DESC"
        
        # 分页
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        
        cursor.execute(query, tuple(params))
        columns = [column[0] for column in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return results
    
    def toggle_star(self, item_id):
        """切换收藏状态"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT is_starred FROM clipboard_history WHERE id = ?", (item_id,))
        current = cursor.fetchone()[0]
        new_value = 0 if current else 1
        cursor.execute("UPDATE clipboard_history SET is_starred = ? WHERE id = ?", (new_value, item_id))
        self.conn.commit()
        return new_value
    
    # 收藏管理方法省略，实际实现时需添加
    # create_collection()
    # add_to_collection()
    # get_collections()
    # etc.

    def create_collection(self, name, parent_id=None):
        """创建新收藏夹"""
        cursor = self.conn.cursor()
        cursor.execute('''
        INSERT INTO collections (name, parent_id) 
        VALUES (?, ?)
        ''', (name, parent_id))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_collections(self, parent_id=None):
        """获取收藏夹列表"""
        cursor = self.conn.cursor()
        
        if parent_id is None:
            cursor.execute('''
            SELECT * FROM collections 
            WHERE parent_id IS NULL 
            ORDER BY created_at DESC
            ''')
        else:
            cursor.execute('''
            SELECT * FROM collections 
            WHERE parent_id = ?
            ORDER BY created_at DESC
            ''', (parent_id,))
            
        columns = [column[0] for column in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return results
    
    def add_to_collection(self, collection_id, history_id):
        """添加历史记录到收藏夹"""
        cursor = self.conn.cursor()
        cursor.execute('''
        INSERT INTO collection_items (collection_id, history_id) 
        VALUES (?, ?)
        ''', (collection_id, history_id))
        self.conn.commit()
        return cursor.lastrowid
    
    def remove_from_collection(self, collection_id, history_id):
        """从收藏夹移除历史记录"""
        cursor = self.conn.cursor()
        cursor.execute('''
        DELETE FROM collection_items 
        WHERE collection_id = ? AND history_id = ?
        ''', (collection_id, history_id))
        self.conn.commit()
        return cursor.rowcount
    
    def get_collection_items(self, collection_id):
        """获取收藏夹中的历史记录"""
        cursor = self.conn.cursor()
        cursor.execute('''
        SELECT h.* 
        FROM clipboard_history h
        JOIN collection_items ci ON ci.history_id = h.id
        WHERE ci.collection_id = ?
        ORDER BY h.timestamp DESC
        ''', (collection_id,))
        
        columns = [column[0] for column in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return results
    # end

    # 添加新方法
    def get_setting(self, key, default=None):
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        result = cursor.fetchone()
        return result[0] if result else default

    def set_setting(self, key, value):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )
        self.conn.commit()

    # end
    
    def cleanup_history(self):
        # 使用用户设置替代硬编码的默认值
        max_items = int(self.get_setting('max_items', Config.MAX_HISTORY_ITEMS))
        max_days = int(self.get_setting('max_days', Config.MAX_HISTORY_DAYS))
        max_storage_mb = int(self.get_setting('max_storage', Config.MAX_STORAGE_MB))
        
        """清理旧的历史记录"""
        cursor = self.conn.cursor()
        
        # 计算数据库大小
        cursor.execute("SELECT SUM(length(content)) + SUM(length(file_path)) FROM clipboard_history")
        total_size_kb = cursor.fetchone()[0] / 1024 if cursor.fetchone()[0] else 0
        
        # 设置默认值
        max_items = Config.MAX_HISTORY_ITEMS
        max_days = Config.MAX_HISTORY_DAYS
        max_storage_mb = Config.MAX_STORAGE_MB
        
        # 读取配置
        # TODO: 从设置表中读取用户配置
        
        # 按数量清理
        cursor.execute("SELECT COUNT(*) FROM clipboard_history")
        total_items = cursor.fetchone()[0]
        if total_items > max_items:
            to_delete = total_items - max_items
            cursor.execute("DELETE FROM clipboard_history WHERE id IN (SELECT id FROM clipboard_history ORDER BY timestamp ASC LIMIT ?)", (to_delete,))
        
        # 按时间清理
        threshold_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("DELETE FROM clipboard_history WHERE timestamp < datetime(?, ?)", (datetime.now().strftime('%Y-%m-%d'), f'-{max_days} days'))
        
        # 按存储空间清理
        if total_size_kb / 1024 > max_storage_mb:
            size_to_free = (total_size_kb - (max_storage_mb * 1024)) * 1024
            deleted_size = 0
            
            cursor.execute("SELECT id, length(content) + length(file_path) as size FROM clipboard_history ORDER BY timestamp ASC")
            for row in cursor.fetchall():
                deleted_size += row[1]
                cursor.execute("DELETE FROM clipboard_history WHERE id = ?", (row[0],))
                # 同时删除备份文件
                # TODO: 添加文件删除逻辑
                if deleted_size >= size_to_free:
                    break
        
        self.conn.commit()
        return cursor.rowcount
    
    def close(self):
        self.conn.close()

# 使用示例
if __name__ == "__main__":
    db = DatabaseManager()
    # 模拟数据
    test_data = {
        "Type": "Text",
        "File": "",
        "Clipboard": "这是一条测试文本",
        "From": "PC"
    }
    item_id = db.add_history_item(test_data)
    print(f"添加记录ID: {item_id}")
    
    history = db.get_history(limit=10)
    print(f"前10条记录: {history}")
    
    db.close()