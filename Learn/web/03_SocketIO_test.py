from flask import Flask
from flask_socketio import SocketIO, emit

# 初始化Flask和SocketIO
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")  # 允许跨域

# 监听客户端发送的history_update事件
@socketio.on('history_update')
def handle_history_update():
    print("✅ 收到通知：history_update")
    # 可以在这里添加回复逻辑
    emit('server_response', {'status': '已收到更新通知'})

if __name__ == '__main__':
    print("测试服务器启动，等待通知...")
    socketio.run(app,port=5000, debug=True)
