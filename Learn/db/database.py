# database.py
"""
SyncClipboard 历史记录功能数据库模块

该模块负责初始化和管理历史记录功能的数据库结构，包括：
- 剪贴板历史记录表
- 备份文件表
- 收藏记录表
- 收藏夹表

使用 SQLModel 作为 ORM 框架，SQLite 作为数据库引擎
"""

import os
from sqlmodel import SQLModel, create_engine, Session, Field, Column, ForeignKey, select, UniqueConstraint
from typing import Optional
from datetime import datetime
from sqlalchemy import DateTime, Text
import uuid as uuid_lib

# 数据库文件路径 - 使用相对路径在当前目录创建数据库文件
DB_FILE = "history.db"
LOG_ENABLED = False  # True 表示启用日志， False 表示禁用

class BaseTable(SQLModel):
    """所有数据库表的基础模型（非表模型，仅用于继承）"""
    id: Optional[int] = Field(
        default=None, # 通过设置为 Optional[int]、default=None，让 SQLModel 处理自增主键
        primary_key=True, 
        description="自增主键"
    )

class ClipboardHistory(BaseTable, table=True):
    """
    剪贴板历史记录表
    
    存储所有剪贴板同步的历史记录
    
    """
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

class BackupFile(BaseTable, table=True):
    """
    备份文件表
    
    存储所有备份文件的信息，与历史记录表通过checksum关联
    
    字段说明：
    - checksum: 文件内容的MD5校验和（主键）
    - filepath: 备份文件的绝对路径
    - size: 文件大小（字节）
    """
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

class Favorite(BaseTable, table=True):
    """
    收藏记录表
    
    存储用户收藏的历史记录，与历史记录表通过UUID关联
    
    字段说明：
    - history_uuid: 关联的历史记录UUID
    - folder_id: 所属收藏夹ID
    - created_at: 收藏时间（自动生成）
    """
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

class Folder(BaseTable, table=True):
    """
    收藏夹表
    
    支持多级收藏夹管理，通过parent_id实现树形结构
    
    字段说明：
    - name: 收藏夹名称
    - parent_id: 父收藏夹ID（0表示根目录）
    - path: 完整路径（如/a/b/），用于快速查询
    """


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

def init_db():
    """
    初始化数据库
    
    功能：
    1. 检测数据库文件是否存在
    2. 创建SQLite数据库引擎
    3. 创建所有表结构（如果不存在）
    4. 初始化根收藏夹（仅当首次创建数据库时）
    
    返回：
    - SQLAlchemy引擎对象
    """
    db_exists = os.path.exists(DB_FILE)
    
    # 创建SQLite数据库引擎
    # echo=True 参数启用SQL日志（生产环境应设为False）
    sqlite_url = f"sqlite:///{DB_FILE}"  # 数据库连接地址
    engine = create_engine(sqlite_url, echo=LOG_ENABLED)  # 创建引擎
    
    # 创建所有表（如果不存在）
    SQLModel.metadata.create_all(engine)
    
    # 初始化收藏夹根目录（仅当首次创建数据库时）
    if not db_exists:
        with Session(engine) as session:
            # 创建根收藏夹
            root_folder = Folder(name="Root", parent_id=0, path="/")
            session.add(root_folder)
            session.commit()
            
            # 更新根收藏夹的path（自引用需要）
            # 路径格式为 /ID/，例如 /1/
            root_folder.path = f"/{root_folder.id}/"
            session.add(root_folder)
            session.commit()
    
    return engine

def test_database_operations(engine):
    """测试数据库的CRUD操作"""
    print("\n=== 开始数据库操作测试 ===")
    
    # 测试1: 添加数据
    print("\n--- 测试添加数据 ---")
    with Session(engine) as session:
        # 添加剪贴板历史记录
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
        print(f"添加了2条剪贴板历史记录 (ID: {text_record.id}, {file_record.id})")
        
        # 添加备份文件记录
        backup = BackupFile(
            checksum="5d41402abc4b2a76b9719d911017c592",
            filepath="/backup/files/5d41402abc4b2a76b9719d911017c592.zip",
            size=10240
        )
        session.add(backup)
        session.commit()
        print(f"添加了1条备份文件记录 (ID: {backup.id})")
        
        # 添加新的收藏夹
        new_folder = Folder(
            name="重要内容",
            parent_id=1,  # 假设根目录ID是1
            path="/1/2/"
        )
        session.add(new_folder)
        session.commit()
        print(f"添加了1个收藏夹 (ID: {new_folder.id}, 名称: {new_folder.name})")
        
        # 添加收藏记录
        favorite = Favorite(
            history_uuid=text_record.uuid,
            folder_id=new_folder.id
        )
        session.add(favorite)
        session.commit()
        print(f"添加了1条收藏记录 (ID: {favorite.id})")
        
        # 保存ID用于后续测试
        text_record_id = text_record.id
        file_record_uuid = file_record.uuid
        folder_id = new_folder.id
        favorite_id = favorite.id

    # 测试2: 查询数据
    print("\n--- 测试查询数据 ---")
    with Session(engine) as session:
        # 查询所有剪贴板历史记录
        history_records = session.exec(select(ClipboardHistory)).all()
        print(f"查询到 {len(history_records)} 条剪贴板历史记录")
        
        # 按类型查询剪贴板记录
        text_records = session.exec(
            select(ClipboardHistory).where(ClipboardHistory.type == "Text")
        ).all()
        print(f"查询到 {len(text_records)} 条文本类型记录")
        
        # 查询特定ID的记录
        specific_record = session.get(ClipboardHistory, text_record_id)
        if specific_record:
            print(f"查询到特定记录: {specific_record.clipboard} (类型: {specific_record.type})")
        
        # 查询收藏夹中的内容
        favorites = session.exec(
            select(Favorite).where(Favorite.folder_id == folder_id)
        ).all()
        print(f"查询到 {len(favorites)} 条收藏记录在 '重要内容' 文件夹中")

    # 测试3: 更新数据
    print("\n--- 测试更新数据 ---")
    with Session(engine) as session:
        # 更新剪贴板记录
        record_to_update = session.get(ClipboardHistory, text_record_id)
        if record_to_update:
            old_content = record_to_update.clipboard
            record_to_update.clipboard = "更新后的测试文本内容"
            record_to_update.tag = "已更新"
            session.commit()
            print(f"更新了记录内容: 从 '{old_content}' 改为 '{record_to_update.clipboard}'")
        
        # 更新收藏夹名称
        folder_to_update = session.get(Folder, folder_id)
        if folder_to_update:
            old_name = folder_to_update.name
            folder_to_update.name = "非常重要的内容"
            session.commit()
            print(f"更新了收藏夹名称: 从 '{old_name}' 改为 '{folder_to_update.name}'")

    # 测试4: 删除数据
    print("\n--- 测试删除数据 ---")
    with Session(engine) as session:
        # 删除收藏记录
        favorite_to_delete = session.get(Favorite, favorite_id)
        if favorite_to_delete:
            session.delete(favorite_to_delete)
            session.commit()
            print(f"删除了ID为 {favorite_id} 的收藏记录")
        
        # 检查是否已删除
        deleted_favorite = session.get(Favorite, favorite_id)
        if not deleted_favorite:
            print("确认收藏记录已删除")
        
        # 删除文件记录（级联测试）
        file_record_to_delete = session.exec(
            select(ClipboardHistory).where(ClipboardHistory.uuid == file_record_uuid)
        ).first()
        if file_record_to_delete:
            session.delete(file_record_to_delete)
            session.commit()
            print(f"删除了UUID为 {file_record_uuid} 的文件记录")

    print("\n=== 数据库操作测试完成 ===")

if __name__ == "__main__":
    print("=== 数据库初始化测试 ===")
    
    # 删除旧数据库文件（方便测试）
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        print(f"已删除旧数据库文件: {DB_FILE}")
    
    # 初始化数据库
    engine = init_db()
    print(f"数据库初始化完成，文件: {DB_FILE}")
    
    # 执行数据库操作测试
    test_database_operations(engine)
    
    print("\n所有测试完成")
    
    print("=== 数据库初始化测试完成 ===")
    print(f"数据库文件已创建: {DB_FILE}")