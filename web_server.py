
from flask import Flask, render_template, request, jsonify, send_from_directory
from database import DatabaseManager
from config import Config

app = Flask(__name__, template_folder=Config.TEMPLATES_DIR, static_folder=Config.STATIC_DIR)

db = DatabaseManager()

@app.route('/')
def index():
    # 获取基本的历史记录
    page = int(request.args.get('page', 1))
    per_page = 30
    offset = (page - 1) * per_page
    
    history = db.get_history(limit=per_page, offset=offset)
    return render_template('index.html', history=history, page=page)

@app.route('/history')
def get_history():
    # 带筛选的历史记录
    filters = {
        'type': request.args.get('type', ''),
        'source': request.args.get('source', ''),
        'start_date': request.args.get('start_date', ''),
        'end_date': request.args.get('end_date', ''),
        'starred': request.args.get('starred', '') == 'true'
    }
    
    history = db.get_history(filters=filters)
    return jsonify(history)

@app.route('/star/<int:item_id>', methods=['POST'])
def toggle_star(item_id):
    new_status = db.toggle_star(item_id)
    return jsonify({'starred': new_status})

@app.route('/download/<path:filename>')
def download_file(filename):
    return send_from_directory(Config.BACKUP_DIR, filename, as_attachment=True)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        # 保存设置
        settings = {
            'max_items': request.form['max_items'],
            'max_days': request.form['max_days'],
            'max_storage': request.form['max_storage']
        }
        
        db.set_setting('max_items', settings['max_items'])
        db.set_setting('max_days', settings['max_days'])
        db.set_setting('max_storage', settings['max_storage'])
        
        return jsonify({'status': 'success'})
    
    # 获取当前设置
    settings_data = {
        'max_items': db.get_setting('max_items', Config.MAX_HISTORY_ITEMS),
        'max_days': db.get_setting('max_days', Config.MAX_HISTORY_DAYS),
        'max_storage': db.get_setting('max_storage', Config.MAX_STORAGE_MB)
    }
    return render_template('settings.html', settings=settings_data)


# 网页服务添加路由
@app.route('/collections', methods=['GET', 'POST'])
def collections():
    if request.method == 'POST':
        name = request.form['name']
        parent_id = request.form.get('parent_id', None)
        db.create_collection(name, parent_id)
        return jsonify({'status': 'success'})
    
    collections = db.get_collections()
    return render_template('collections.html', collections=collections)

@app.route('/collection/<int:collection_id>')
def view_collection(collection_id):
    items = db.get_collection_items(collection_id)
    return render_template('collection.html', items=items, collection_id=collection_id)

@app.route('/collection/add', methods=['POST'])
def add_to_collection():
    collection_id = request.form['collection_id']
    history_id = request.form['history_id']
    db.add_to_collection(collection_id, history_id)
    return jsonify({'status': 'success'})

@app.route('/collection/remove', methods=['POST'])
def remove_from_collection():
    collection_id = request.form['collection_id']
    history_id = request.form['history_id']
    db.remove_from_collection(collection_id, history_id)
    return jsonify({'status': 'success'})


if __name__ == '__main__':
    app.run(port=5000, debug=True)

