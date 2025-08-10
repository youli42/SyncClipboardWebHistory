-- 剪贴板项目表
CREATE TABLE clipboard_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    file_name TEXT,
    type TEXT NOT NULL, -- Text, Image, File
    source TEXT, -- 来源信息
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_favorite INTEGER DEFAULT 0,
    file_hash TEXT
);

-- 收藏夹表
CREATE TABLE favorites_folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    parent_id INTEGER,
    FOREIGN KEY (parent_id) REFERENCES favorites_folders (id)
);

-- 收藏项目关联表
CREATE TABLE favorite_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    folder_id INTEGER NOT NULL,
    FOREIGN KEY (item_id) REFERENCES clipboard_items (id),
    FOREIGN KEY (folder_id) REFERENCES favorites_folders (id)
);

-- 应用设置表
CREATE TABLE app_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    max_history_items INTEGER DEFAULT 1000,
    max_storage_days INTEGER DEFAULT 30,
    max_storage_size INTEGER DEFAULT 1024 -- MB
);
