# interactionWeb.py
from flask import Flask, render_template, request, jsonify
import sys
import os

# 获取当前脚本所在目录的绝对路径
current_dir = os.path.dirname(os.path.abspath(__file__))

# 向上三级：当前目录 → 父目录 → 父父目录 → 父父父目录（目标目录）
target_dir = os.path.abspath(
    os.path.join(current_dir, "..", "..", "..")  # ".." 表示上一级目录，三个".."即向上三级
)

# 将目标目录添加到 Python 模块搜索路径
if target_dir not in sys.path:
    sys.path.append(target_dir)

from database import ServerGet

app = Flask(__name__)

@app.route('/')
def index():
    """渲染主页面"""
    return render_template('index.html')

@app.route('/query', methods=['POST'])
def query_history():
    """处理查询请求"""
    try:
        # 获取前端传来的 ID
            # request.form.get('id') # 从 POST 请求中获取前端传递的 ID（request是 Flask 提供的对象，用于解析请求数据）。
            # int(······) # 将获取到的 ID 转换为整数类型，若转换失败，捕获 ValueError 并返回错误信息
        history_id = int(request.form.get('id')) 
        
        # 调用数据库查询函数
        db = ServerGet() # 实例化数据库连接
        result = db.get_history_by_id(history_id)
        
        # 通过jsonify将结果转换为 JSON 格式返回给前端：
            # 若查询成功：{'success': True, 'data': result}（result为数据库记录）。
            # 若查询失败：{'success': False, 'message': '错误信息'}。
        if result:
            return jsonify({
                'success': True,
                'data': result
            })
        else:
            return jsonify({
                'success': False,
                'message': f'未找到 ID 为 {history_id} 的记录'
            })
            
    except ValueError:
        return jsonify({
            'success': False,
            'message': '请输入有效的数字 ID'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        })

if __name__ == '__main__':
    app.run(debug=True)