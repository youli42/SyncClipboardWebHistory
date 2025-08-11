
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

def add_history_item_from_json(data: dict, engine=None):
    """
    将SyncClipboard.json的内容写入数据库，自动处理文本、文件、图片类型。
    :param data: 解析后的JSON字典
    :param engine: 可选，传入SQLModel数据库引擎，否则自动init_db
    """
    if engine is None:
        engine = init_db()
    with Session(engine) as session:
        item_type = data.get("Type", "")
        file_name = data.get("File", "")
        clipboard = data.get("Clipboard", "")
        from_equipment = data.get("From", None)
        tag = data.get("Tag", None)
        raw_content = json.dumps(data, ensure_ascii=False)
        checksum = None

        # 处理文件/图片类型
        if item_type in ["File", "Image"] and file_name:
            # clipboard字段本身就是MD5，无需再算
            checksum = clipboard
            src_path = os.path.join(os.path.dirname(Config.SYNC_CLIPBOARD_JSON_PATH), "file", file_name)
            exists = session.exec(select(BackupFile).where(BackupFile.checksum == checksum)).first()
            backup_name = file_name
            backup_path = os.path.join(Config.BACKUP_DIR, backup_name)
            os.makedirs(Config.BACKUP_DIR, exist_ok=True)
            if not exists and os.path.exists(src_path):
                # 文件名冲突且内容不同，加后缀
                base, ext = os.path.splitext(file_name)
                count = 1
                while os.path.exists(backup_path):
                    # 检查已存在的文件内容是否相同
                    with open(backup_path, "rb") as f:
                        if hashlib.md5(f.read()).hexdigest() == checksum:
                            break
                    backup_name = f"{base}_{count}{ext}"
                    backup_path = os.path.join(Config.BACKUP_DIR, backup_name)
                    count += 1
                if not os.path.exists(backup_path):
                    shutil.copy2(src_path, backup_path)
                size = os.path.getsize(backup_path)
                backup = BackupFile(
                    checksum=checksum,
                    filepath=backup_path,
                    size=size
                )
                session.add(backup)
            elif not os.path.exists(src_path):
                print(f"文件未找到: {src_path}")

        # group类型（多文件压缩包），需要计算MD5
        elif item_type == "Group" and file_name:
            src_path = os.path.join(os.path.dirname(Config.SYNC_CLIPBOARD_JSON_PATH), "file", file_name)
            if os.path.exists(src_path):
                with open(src_path, "rb") as f:
                    file_bytes = f.read()
                    checksum = hashlib.md5(file_bytes).hexdigest()
                exists = session.exec(select(BackupFile).where(BackupFile.checksum == checksum)).first()
                backup_name = file_name
                backup_path = os.path.join(Config.BACKUP_DIR, backup_name)
                os.makedirs(Config.BACKUP_DIR, exist_ok=True)
                if not exists:
                    base, ext = os.path.splitext(file_name)
                    count = 1
                    while os.path.exists(backup_path):
                        with open(backup_path, "rb") as f:
                            if hashlib.md5(f.read()).hexdigest() == checksum:
                                break
                        backup_name = f"{base}_{count}{ext}"
                        backup_path = os.path.join(Config.BACKUP_DIR, backup_name)
                        count += 1
                    if not os.path.exists(backup_path):
                        shutil.copy2(src_path, backup_path)
                    size = os.path.getsize(backup_path)
                    backup = BackupFile(
                        checksum=checksum,
                        filepath=backup_path,
                        size=size
                    )
                    session.add(backup)
            else:
                print(f"文件未找到: {src_path}")

        # 写入历史表
        history = ClipboardHistory(
            raw_content=raw_content,
            clipboard=clipboard,
            type=item_type,
            from_equipment=from_equipment,
            tag=tag,
            checksum=checksum
        )
        session.add(history)
        session.commit()
        return history.id

class ServerGet:
    def __init__(self):
        self.engine = create_engine(f"sqlite:///{Config.DB_PATH}", echo=False)

    def get_history(self, limit=30, offset=0, filters=None):
        with Session(self.engine) as session:
            query = select(ClipboardHistory).order_by(ClipboardHistory.timestamp.desc())
            # 可根据 filters 添加筛选条件
            if filters:
                if filters.get('type'):
                    query = query.where(ClipboardHistory.type == filters['type'])
                if filters.get('source'):
                    query = query.where(ClipboardHistory.from_equipment == filters['source'])
                # 你可以继续扩展更多筛选条件
            results = session.exec(query.offset(offset).limit(limit)).all()
            # 转为 dict 方便模板渲染
            history = []
            for item in results:
                history.append({
                    'id': item.id,
                    'type': item.type,
                    'timestamp': item.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'source': item.from_equipment,
                    'is_favorite': False,  # 你可以根据收藏表判断
                    'content': item.clipboard if item.type == 'Text' else None,
                    'file_name': None,     # 你可以根据 raw_content 或 backup_file 表获取
                })
            return history

    # 根据 ID 获取历史记录
    def get_history_by_id(self, history_id: int):
        with Session(self.engine) as session: # 通过 Session 类创建一个数据库会话（session），self.engine 是数据库引擎（已在类中初始化），用于建立与数据库的连接。with 语句确保会话使用完毕后自动关闭，释放资源。
            # 使用 SQLModel 的 select 方法构建查询语句，指定查询 ClipboardHistory 模型（对应数据库表），并通过 where 条件筛选出 id 等于 history_id 的记录。
            statement = select(ClipboardHistory).where(ClipboardHistory.id == history_id)
            result = session.exec(statement).first() # 通过会话的 exec 方法执行查询语句，first() 方法获取查询结果中的第一条记录（因为 id 通常是唯一的，所以最多只有一条结果）。
            
            if result:
                # 将结果转换为字典格式
                return {
                    'id': result.id,
                    'uuid': result.uuid,
                    'type': result.type,
                    'clipboard': result.clipboard,
                    'from_equipment': result.from_equipment,
                    'tag': result.tag,
                    'timestamp': result.timestamp.isoformat(),
                    'checksum': result.checksum,
                    'raw_content': result.raw_content
                }
            return None

class ServerSet:
    def __init__(self):
        return 0

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
    
# 使用示例
if __name__ == "__main__":
    # 初始化数据库
    engine = init_db()
    
    # 测试数据库操作
    test_database_operations(engine)
