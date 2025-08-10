from flask import Flask, render_template, request, redirect, url_for, jsonify
from datetime import datetime
import os
import json
import sqlite3
from pathlib import Path

app = Flask(__name__)
app.config['DATABASE'] = 'clipboard_history.db'
app.config['UPLOAD_FOLDER'] = 'static/backups'

# 确保备份文件夹存在
Path(app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)

# 数据库初始化
def init_db():
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()

def get_db():
    db = sqlite3.connect(app.config['DATABASE'])
    db.row_factory = sqlite3.Row
    return db

# 路由
@app.route('/')
def index():
    """展示历史记录页面"""
    # 从数据库获取历史记录
    # db = get_db()
    # records = db.execute('SELECT * FROM clipboard_items ORDER BY timestamp DESC').fetchall()
    # db.close()

    """展示历史记录页面"""
    # 模拟数据（替换数据库查询）
    records = [
        {
            'id': 1,
            'type': 'Text',
            'timestamp': '2023-05-15 14:30:22',
            'source': 'Chrome',
            'is_favorite': True,
            'content': '这是一段示例文本内容，用于测试历史记录展示功能。',
            'file_name': None
        },
        {
            'id': 2,
            'type': 'Image',
            'timestamp': '2023-05-14 09:15:47',
            'source': 'Photoshop',
            'is_favorite': False,
            'content': None,
            'file_name': 'screenshot.png'
        },
        {
            'id': 3,
            'type': 'File',
            'timestamp': '2023-05-13 16:20:33',
            'source': 'Finder',
            'is_favorite': False,
            'content': None,
            'file_name': 'document.pdf'
        }
    ]
    
    return render_template('index.html', 
                          records=records, 
                          active_page='history')

@app.route('/favorites')
def favorites():
    """展示收藏页面"""
    db = get_db()
    records = db.execute('SELECT * FROM clipboard_items WHERE is_favorite = 1 ORDER BY timestamp DESC').fetchall()
    db.close()
    
    return render_template('favorites.html', 
                          records=records, 
                          active_page='favorites')

@app.route('/settings')
def settings():
    """展示设置页面"""
    # 从数据库获取设置
    db = get_db()
    settings = db.execute('SELECT * FROM app_settings').fetchone()
    db.close()
    
    # 如果没有设置，使用默认值
    if not settings:
        settings = {
            'max_history_items': 1000,
            'max_storage_days': 30,
            'max_storage_size': 1024  # MB
        }
    
    return render_template('settings.html', 
                          settings=settings, 
                          active_page='settings')

@app.route('/toggle_favorite/<int:item_id>')
def toggle_favorite(item_id):
    """切换项目的收藏状态"""
    db = get_db()
    item = db.execute('SELECT is_favorite FROM clipboard_items WHERE id = ?', (item_id,)).fetchone()
    
    if item:
        new_state = 0 if item['is_favorite'] else 1
        db.execute('UPDATE clipboard_items SET is_favorite = ? WHERE id = ?', (new_state, item_id))
        db.commit()
    
    db.close()
    return redirect(request.referrer or url_for('index'))

@app.route('/update_settings', methods=['POST'])
def update_settings():
    """更新应用设置"""
    max_history = request.form.get('max_history_items', type=int)
    max_days = request.form.get('max_storage_days', type=int)
    max_size = request.form.get('max_storage_size', type=int)
    
    db = get_db()
    # 检查是否已有设置记录
    existing = db.execute('SELECT id FROM app_settings').fetchone()
    
    if existing:
        db.execute('''
            UPDATE app_settings 
            SET max_history_items = ?, max_storage_days = ?, max_storage_size = ?
            WHERE id = ?
        ''', (max_history, max_days, max_size, existing['id']))
    else:
        db.execute('''
            INSERT INTO app_settings (max_history_items, max_storage_days, max_storage_size)
            VALUES (?, ?, ?)
        ''', (max_history, max_days, max_size))
    
    db.commit()
    db.close()
    
    return redirect(url_for('settings'))

@app.route('/download/<int:item_id>')
def download_file(item_id):
    """下载文件或图片"""
    db = get_db()
    item = db.execute('SELECT * FROM clipboard_items WHERE id = ?', (item_id,)).fetchone()
    db.close()
    
    if not item or not item['file_name'] or item['type'] not in ['File', 'Image']:
        return "文件不存在或不支持下载", 404
    
    # 实际应用中这里应该处理文件下载逻辑
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], item['file_name'])
    if not os.path.exists(file_path):
        return "文件已被删除或移动", 404
    
    # 简化处理，实际应使用send_from_directory
    return f"下载文件: {item['file_name']} (实际应用中会触发文件下载)"

@app.context_processor
def inject_now():
    return {'now': datetime.utcnow()}

if __name__ == '__main__':
    # 确保数据库和表存在
    if not os.path.exists(app.config['DATABASE']):
        init_db()
    app.run(debug=True)
