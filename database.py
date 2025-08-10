
import os
from sqlalchemy import DateTime, Text, delete
from sqlmodel import SQLModel, create_engine, Session, Field, Column, ForeignKey, select, UniqueConstraint
from typing import Optional
from datetime import datetime
from config import Config
import shutil
import uuid as uuid_lib
import hashlib
import json

class BaseTable(SQLModel):
    """所有数据库表的基础模型（非表模型，仅用于继承）"""
    id: Optional[int] = Field(
        default=None, # 通过设置为 Optional[int]、default=None，让 SQLModel 处理自增主键
        primary_key=True, 
        description="自增主键"
    )

# 历史记录表
class ClipboardHistory(BaseTable, table=True):

    # __tablename__ = "ClipboardHistory"  # 显式指定表名
    raw_content: str = Field(
        sa_column=Column(Text), # 将 raw_content 定义为 TEXT 类型（适合存储长文本）
        description="原始JSON内容"
    )
    uuid: str = Field(
        default_factory=lambda: str(uuid_lib.uuid4()),  # 自动生成UUID
        nullable=False,
        unique=True,
        description="全局唯一标识符"
    )
    clipboard: str = Field(description="剪贴板内容")
    type: str = Field(nullable=False, description="记录类型: Text/Image/File")
    from_equipment: Optional[str] = Field(
        default=None, 
        description="来源设备"
    )
    tag: Optional[str] = Field( # 声明为可选字段
        default=None,
        description="记录标签（可选）"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,  # 自动设置当前时间
        sa_column=Column(DateTime(timezone=True)),
        description="记录时间"
    )
    checksum: Optional[str] = Field(
        default=None,
        description="文件内容的MD5校验和",
        index=True  # 创建索引加速查询
    )
    
    class Config:
        # 为时间戳字段创建索引，优化按时间筛选的性能
        indexes = [("timestamp_index", "timestamp")]

# 备份文件表
class BackupFile(BaseTable, table=True):

    __tablename__ = "backup_files"  # 显式指定表名
    checksum: str = Field(
        unique=True,  # 改为唯一约束而非主键
        index=True,   # 添加索引加速查询
        description="文件内容的MD5校验和"
    )
    filepath: str = Field(
        # unique=True,  # 确保文件路径唯一
        nullable=False,
        description="备份文件绝对路径"
    )
    size: int = Field(description="文件大小(字节)")

# 收藏记录表
class Favorite(BaseTable, table=True):

    __tablename__ = "favorites"  # 显式指定表名
    history_uuid: str = Field(
        foreign_key="clipboardhistory.uuid",  # 外键关联历史记录表
        nullable=False,
        description="关联的历史记录UUID"
    )
    folder_id: int = Field(
        foreign_key="folder.id",  # 外键关联收藏夹表
        description="所属收藏夹ID"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,  # 自动设置当前时间
        sa_column=Column(DateTime(timezone=True)),
        description="收藏时间"
    )
    
    # 唯一约束防止重复收藏（同一记录不能在同一个收藏夹收藏多次）
    __table_args__ = (
        UniqueConstraint('history_uuid', 'folder_id', name='_favorite_unique'),
    )

# 收藏夹表
class Folder(BaseTable, table=True):

    name: str = Field(nullable=False, description="收藏夹名称")
    parent_id: int = Field(
        default=0,
        foreign_key="folder.id",  # 自引用外键，实现多级结构
        description="父收藏夹ID（0为根）"
    )
    path: Optional[str] = Field(
        default=None, 
        description="完整路径（如/a/b/）"
    )

def init_db(): # 初始化数据库
    db_exists = os.path.exists(Config.DB_PATH)
    
    # 创建SQLite数据库引擎
    # echo=True 参数启用SQL日志（生产环境应设为False）
    sqlite_url = f"sqlite:///{Config.DB_PATH}"  # 数据库连接地址
    engine = create_engine(sqlite_url, echo=Config.DB_LOG_ENABLED)  # 创建引擎
    
    # 创建所有表（如果不存在）
    SQLModel.metadata.create_all(engine)
    
    # 初始化收藏夹根目录（仅当首次创建数据库时）
    if not db_exists:
        with Session(engine) as session:
            # 创建根收藏夹
            root_folder = Folder(name="Root", parent_id=None, path="/") # 使用 None 而不是 0 作为外键，避免约束报错
            session.add(root_folder)
            session.commit()
            
            # 更新根收藏夹的path（自引用需要）
            # 路径格式为 /ID/，例如 /1/
            root_folder.path = f"/{root_folder.id}/"
            session.add(root_folder)
            session.commit()
    
    return engine


def print_all_tables(engine):
    """输出所有表的内容"""
    with Session(engine) as session:
        print("\n--- 当前 ClipboardHistory 表 ---")
        for row in session.exec(select(ClipboardHistory)).all():
            print(row.__dict__)
        print("\n--- 当前 BackupFile 表 ---")
        for row in session.exec(select(BackupFile)).all():
            print(row.__dict__)
        print("\n--- 当前 Folder 表 ---")
        for row in session.exec(select(Folder)).all():
            print(row.__dict__)
        print("\n--- 当前 Favorite 表 ---")
        for row in session.exec(select(Favorite)).all():
            print(row.__dict__)

def test_database_operations(engine):
    print("\n=== 开始数据库操作测试 ===")

    # 测试前清理数据，避免唯一约束冲突
    with Session(engine) as session:
        session.exec(delete(Favorite))
        session.exec(delete(BackupFile))
        session.exec(delete(ClipboardHistory))
        session.exec(delete(Folder).where(Folder.id != 1))
        session.commit()

    print("\n[清理后数据库状态]")
    print_all_tables(engine)

    # 1. 添加数据
    print("\n--- 测试添加数据 ---")
    with Session(engine) as session:
        text_record = ClipboardHistory(
            clipboard="测试文本内容",
            raw_content='{"Text":"测试内容"}',
            type="Text",
            from_equipment="PC-Desktop",
            tag="测试"
        )
        file_record = ClipboardHistory(
            clipboard="example.zip",
            raw_content='{"File":"example.zip","Type":"File"}',
            type="File",
            from_equipment="Laptop-Mac",
            checksum="5d41402abc4b2a76b9719d911017c592"
        )
        session.add(text_record)
        session.add(file_record)
        session.commit()

        backup = BackupFile(
            checksum="5d41402abc4b2a76b9719d911017c592",
            filepath="/backup/files/5d41402abc4b2a76b9719d911017c592.zip",
            size=10240
        )
        session.add(backup)
        session.commit()

        new_folder = Folder(
            name="重要内容",
            parent_id=1,
            path="/1/2/"
        )
        session.add(new_folder)
        session.commit()

        favorite = Favorite(
            history_uuid=text_record.uuid,
            folder_id=new_folder.id
        )
        session.add(favorite)
        session.commit()

        # 保存ID用于后续测试
        text_record_id = text_record.id
        file_record_uuid = file_record.uuid
        folder_id = new_folder.id
        favorite_id = favorite.id

    print("\n[添加数据后数据库状态]")
    print_all_tables(engine)

    # 2. 查询数据
    print("\n--- 测试查询数据 ---")
    with Session(engine) as session:
        history_records = session.exec(select(ClipboardHistory)).all()
        print(f"查询到 {len(history_records)} 条剪贴板历史记录")
        text_records = session.exec(
            select(ClipboardHistory).where(ClipboardHistory.type == "Text")
        ).all()
        print(f"查询到 {len(text_records)} 条文本类型记录")
        specific_record = session.get(ClipboardHistory, text_record_id)
        if specific_record:
            print(f"查询到特定记录: {specific_record.clipboard} (类型: {specific_record.type})")
        favorites = session.exec(
            select(Favorite).where(Favorite.folder_id == folder_id)
        ).all()
        print(f"查询到 {len(favorites)} 条收藏记录在 '重要内容' 文件夹中")
    print("\n[查询后数据库状态]")
    print_all_tables(engine)

    # 3. 更新数据
    print("\n--- 测试更新数据 ---")
    with Session(engine) as session:
        record_to_update = session.get(ClipboardHistory, text_record_id)
        if record_to_update:
            old_content = record_to_update.clipboard
            record_to_update.clipboard = "更新后的测试文本内容"
            record_to_update.tag = "已更新"
            session.commit()
            print(f"更新了记录内容: 从 '{old_content}' 改为 '{record_to_update.clipboard}'")
        folder_to_update = session.get(Folder, folder_id)
        if folder_to_update:
            old_name = folder_to_update.name
            folder_to_update.name = "非常重要的内容"
            session.commit()
            print(f"更新了收藏夹名称: 从 '{old_name}' 改为 '{folder_to_update.name}'")
    print("\n[更新数据后数据库状态]")
    print_all_tables(engine)

    # 4. 删除数据
    print("\n--- 测试删除数据 ---")
    with Session(engine) as session:
        favorite_to_delete = session.get(Favorite, favorite_id)
        if favorite_to_delete:
            session.delete(favorite_to_delete)
            session.commit()
            print(f"删除了ID为 {favorite_id} 的收藏记录")
        deleted_favorite = session.get(Favorite, favorite_id)
        if not deleted_favorite:
            print("确认收藏记录已删除")
        file_record_to_delete = session.exec(
            select(ClipboardHistory).where(ClipboardHistory.uuid == file_record_uuid)
        ).first()
        if file_record_to_delete:
            session.delete(file_record_to_delete)
            session.commit()
            print(f"删除了UUID为 {file_record_uuid} 的文件记录")
    print("\n[删除数据后数据库状态]")
    print_all_tables(engine)

    print("\n=== 数据库操作测试完成 ===")



# class DatabseManager:
#     def __init__(self):
#         os.makedirs(os.path.dirname(Config.DB_PATH), exist_ok=True)
#         os.makedirs(Config.BACKUP_DIR, exist_ok=True)
#         self.conn = sqlite3.connect(Config.DB_PATH)
#         self.create_tables()

#         # 配置页面功能
#         cursor = self.conn.cursor()  # 修复：先获取游标
#         cursor.execute('''
#             CREATE TABLE IF NOT EXISTS settings (
#                 key TEXT PRIMARY KEY,
#                 value TEXT
#             )
#         ''')
#         self.conn.commit()
        
#     def create_tables(self):
#         cursor = self.conn.cursor()
#         cursor.execute('''
#         CREATE TABLE IF NOT EXISTS clipboard_history (
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             type TEXT NOT NULL,
#             content TEXT,
#             file_path TEXT,
#             from_source TEXT,
#             timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
#             is_starred BOOLEAN DEFAULT 0
#         )
#         ''')
        
#         cursor.execute('''
#         CREATE TABLE IF NOT EXISTS collections (
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             name TEXT NOT NULL,
#             parent_id INTEGER DEFAULT NULL,
#             created_at DATETIME DEFAULT CURRENT_TIMESTAMP
#         )
#         ''')
        
#         cursor.execute('''
#         CREATE TABLE IF NOT EXISTS collection_items (
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             collection_id INTEGER NOT NULL,
#             history_id INTEGER NOT NULL,
#             FOREIGN KEY(collection_id) REFERENCES collections(id),
#             FOREIGN KEY(history_id) REFERENCES clipboard_history(id)
#         )
#         ''')
        
#         self.conn.commit()
    
#     def add_history_item(self, data):
#         """添加新的剪贴板历史记录"""
#         cursor = self.conn.cursor()
        
#         # 提取数据
#         item_type = data.get("Type", "")
#         file_name = data.get("File", "")
#         clipboard = data.get("Clipboard", "")
#         from_source = data.get("From", "")
#         tags = data.get("Tag", "")
        
#         # 备份文件（如果是图片或文件）
#         backup_path = None
#         if item_type in ["Image", "File"]:
#             original_path = os.path.join("file", clipboard)
#             if os.path.exists(original_path):
#                 # 生成唯一的备份文件名
#                 ext = os.path.splitext(file_name)[1] if file_name else ""
#                 unique_name = f"{uuid.uuid4().hex}{ext}"
#                 backup_path = os.path.join(Config.BACKUP_DIR, unique_name)
                
#                 # 复制文件到备份目录
#                 shutil.copy2(original_path, backup_path)
        
#         # 准备要插入的内容
#         content = file_name if item_type != "Text" else clipboard
        
#         cursor.execute('''
#         INSERT INTO clipboard_history 
#         (type, content, file_path, from_source, timestamp) 
#         VALUES (?, ?, ?, ?, datetime('now'))
#         ''', (item_type, content, backup_path, from_source))
        
#         self.conn.commit()
#         return cursor.lastrowid
    
#     def get_history(self, limit=None, offset=0, filters=None):
#         """获取历史记录"""
#         cursor = self.conn.cursor()
#         query = "SELECT * FROM clipboard_history"
#         params = []
        
#         # 构建过滤条件
#         conditions = []
#         if filters:
#             if "type" in filters and filters["type"]:
#                 conditions.append("type = ?")
#                 params.append(filters["type"])
#             if "source" in filters and filters["source"]:
#                 conditions.append("from_source = ?")
#                 params.append(filters["source"])
#             if "start_date" in filters and filters["start_date"]:
#                 conditions.append("DATE(timestamp) >= ?")
#                 params.append(filters["start_date"])
#             if "end_date" in filters and filters["end_date"]:
#                 conditions.append("DATE(timestamp) <= ?")
#                 params.append(filters["end_date"])
#             if "starred" in filters and filters["starred"]:
#                 conditions.append("is_starred = 1")
        
#         if conditions:
#             query += " WHERE " + " AND ".join(conditions)
        
#         # 排序
#         query += " ORDER BY timestamp DESC"
        
#         # 分页
#         if limit is not None:
#             query += " LIMIT ? OFFSET ?"
#             params.extend([limit, offset])
        
#         cursor.execute(query, tuple(params))
#         columns = [column[0] for column in cursor.description]
#         results = [dict(zip(columns, row)) for row in cursor.fetchall()]
#         return results
    
#     def toggle_star(self, item_id):
#         """切换收藏状态"""
#         cursor = self.conn.cursor()
#         cursor.execute("SELECT is_starred FROM clipboard_history WHERE id = ?", (item_id,))
#         current = cursor.fetchone()[0]
#         new_value = 0 if current else 1
#         cursor.execute("UPDATE clipboard_history SET is_starred = ? WHERE id = ?", (new_value, item_id))
#         self.conn.commit()
#         return new_value
    
#     # 收藏管理方法省略，实际实现时需添加
#     # create_collection()
#     # add_to_collection()
#     # get_collections()
#     # etc.

#     def create_collection(self, name, parent_id=None):
#         """创建新收藏夹"""
#         cursor = self.conn.cursor()
#         cursor.execute('''
#         INSERT INTO collections (name, parent_id) 
#         VALUES (?, ?)
#         ''', (name, parent_id))
#         self.conn.commit()
#         return cursor.lastrowid
    
#     def get_collections(self, parent_id=None):
#         """获取收藏夹列表"""
#         cursor = self.conn.cursor()
        
#         if parent_id is None:
#             cursor.execute('''
#             SELECT * FROM collections 
#             WHERE parent_id IS NULL 
#             ORDER BY created_at DESC
#             ''')
#         else:
#             cursor.execute('''
#             SELECT * FROM collections 
#             WHERE parent_id = ?
#             ORDER BY created_at DESC
#             ''', (parent_id,))
            
#         columns = [column[0] for column in cursor.description]
#         results = [dict(zip(columns, row)) for row in cursor.fetchall()]
#         return results
    
#     def add_to_collection(self, collection_id, history_id):
#         """添加历史记录到收藏夹"""
#         cursor = self.conn.cursor()
#         cursor.execute('''
#         INSERT INTO collection_items (collection_id, history_id) 
#         VALUES (?, ?)
#         ''', (collection_id, history_id))
#         self.conn.commit()
#         return cursor.lastrowid
    
#     def remove_from_collection(self, collection_id, history_id):
#         """从收藏夹移除历史记录"""
#         cursor = self.conn.cursor()
#         cursor.execute('''
#         DELETE FROM collection_items 
#         WHERE collection_id = ? AND history_id = ?
#         ''', (collection_id, history_id))
#         self.conn.commit()
#         return cursor.rowcount
    
#     def get_collection_items(self, collection_id):
#         """获取收藏夹中的历史记录"""
#         cursor = self.conn.cursor()
#         cursor.execute('''
#         SELECT h.* 
#         FROM clipboard_history h
#         JOIN collection_items ci ON ci.history_id = h.id
#         WHERE ci.collection_id = ?
#         ORDER BY h.timestamp DESC
#         ''', (collection_id,))
        
#         columns = [column[0] for column in cursor.description]
#         results = [dict(zip(columns, row)) for row in cursor.fetchall()]
#         return results
#     # end

#     # 添加新方法
#     def get_setting(self, key, default=None):
#         cursor = self.conn.cursor()
#         cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
#         result = cursor.fetchone()
#         return result[0] if result else default

#     def set_setting(self, key, value):
#         cursor = self.conn.cursor()
#         cursor.execute(
#             "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
#             (key, value)
#         )
#         self.conn.commit()

#     # end
    
#     def cleanup_history(self):
#         # 使用用户设置替代硬编码的默认值
#         max_items = int(self.get_setting('max_items', Config.MAX_HISTORY_ITEMS))
#         max_days = int(self.get_setting('max_days', Config.MAX_HISTORY_DAYS))
#         max_storage_mb = int(self.get_setting('max_storage', Config.MAX_STORAGE_MB))
        
#         """清理旧的历史记录"""
#         cursor = self.conn.cursor()
        
#         # 计算数据库大小
#         cursor.execute("SELECT SUM(length(content)) + SUM(length(file_path)) FROM clipboard_history")
#         total_size_kb = cursor.fetchone()[0] / 1024 if cursor.fetchone()[0] else 0
        
#         # 设置默认值
#         max_items = Config.MAX_HISTORY_ITEMS
#         max_days = Config.MAX_HISTORY_DAYS
#         max_storage_mb = Config.MAX_STORAGE_MB
        
#         # 读取配置
#         # TODO: 从设置表中读取用户配置
        
#         # 按数量清理
#         cursor.execute("SELECT COUNT(*) FROM clipboard_history")
#         total_items = cursor.fetchone()[0]
#         if total_items > max_items:
#             to_delete = total_items - max_items
#             cursor.execute("DELETE FROM clipboard_history WHERE id IN (SELECT id FROM clipboard_history ORDER BY timestamp ASC LIMIT ?)", (to_delete,))
        
#         # 按时间清理
#         threshold_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
#         cursor.execute("DELETE FROM clipboard_history WHERE timestamp < datetime(?, ?)", (datetime.now().strftime('%Y-%m-%d'), f'-{max_days} days'))
        
#         # 按存储空间清理
#         if total_size_kb / 1024 > max_storage_mb:
#             size_to_free = (total_size_kb - (max_storage_mb * 1024)) * 1024
#             deleted_size = 0
            
#             cursor.execute("SELECT id, length(content) + length(file_path) as size FROM clipboard_history ORDER BY timestamp ASC")
#             for row in cursor.fetchall():
#                 deleted_size += row[1]
#                 cursor.execute("DELETE FROM clipboard_history WHERE id = ?", (row[0],))
#                 # 同时删除备份文件
#                 # TODO: 添加文件删除逻辑
#                 if deleted_size >= size_to_free:
#                     break
        
#         self.conn.commit()
#         return cursor.rowcount
    
#     def close(self):
#         self.conn.close()
        


# 使用示例
if __name__ == "__main__":
    # 初始化数据库
    engine = init_db()
    
    # 测试数据库操作
    test_database_operations(engine)
