from flask import Flask, render_template, request, redirect, url_for, jsonify
from datetime import datetime, timedelta
import os
import json
import sqlite3
from pathlib import Path
import random # test data

app = Flask(__name__)
app.config['DATABASE'] = 'clipboard_history.db'
app.config['UPLOAD_FOLDER'] = 'static/backups'

def generate_test_records(count=500):
    records = []
    types = ['Text', 'Image', 'File']
    sources = ['Chrome', 'Photoshop', 'Finder', 'Word', 'Excel', 'PowerPoint', 'Firefox', 'Safari', 'VS Code', 'Terminal']
    
    # 生成过去30天内的随机时间
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    for i in range(1, count + 1):
        record_type = random.choice(types)
        timestamp = start_date + timedelta(seconds=random.randint(0, 30*24*3600))
        
        record = {
            'id': i,
            'type': record_type,
            'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'source': random.choice(sources),
            'is_favorite': random.choice([True, False]),
            'content': None,
            'file_name': None
        }
        
        # 根据类型设置内容或文件名
        if record_type == 'Text':
            record['content'] = f"这是第{i}条文本记录，用于测试历史记录展示功能。这是一段示例文本内容，包含随机生成的信息。"
        elif record_type == 'Image':
            img_formats = ['png', 'jpg', 'jpeg', 'gif', 'svg']
            record['file_name'] = f"image_{i}.{random.choice(img_formats)}"
        elif record_type == 'File':
            file_formats = ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'zip', 'rar', 'txt']
            record['file_name'] = f"document_{i}.{random.choice(file_formats)}"
        
        records.append(record)
    
    return records

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
    # 生成500条测试数据
    records = generate_test_records(100)
    # print(records)
    # 获取筛选参数
    filter_type = request.args.get('type', 'all')
    filter_source = request.args.get('source', 'all')
    filter_time = request.args.get('time', 'all')
    
    # 构建查询
    query = 'SELECT * FROM clipboard_items WHERE 1=1'
    params = []
    
    if filter_type != 'all':
        query += ' AND type = ?'
        params.append(filter_type.capitalize())
    
    if filter_source != 'all':
        if filter_source == 'Nova11':
            query += ' AND source = ?'
            params.append('Nova11')
        else:
            query += ' AND source != ?'
            params.append('Nova11')
    
    # 时间筛选逻辑
    now = datetime.now()
    if filter_time == 'today':
        today_start = datetime(now.year, now.month, now.day)
        query += ' AND timestamp >= ?'
        params.append(today_start)
    elif filter_time == 'week':
        week_start = now - timedelta(days=now.weekday())
        week_start = datetime(week_start.year, week_start.month, week_start.day)
        query += ' AND timestamp >= ?'
        params.append(week_start)
    elif filter_time == 'month':
        month_start = datetime(now.year, now.month, 1)
        query += ' AND timestamp >= ?'
        params.append(month_start)
    
    query += ' ORDER BY timestamp DESC'
    
    # # 执行查询
    # db = get_db()
    # records = db.execute(query, tuple(params)).fetchall()
    # db.close()
    
    return render_template('index.html', records=records, active_page='history')

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
