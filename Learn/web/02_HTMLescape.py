from flask import Flask # 导入了 Flask 类。该类的实例将会成为我们的 WSGI 应用。
from datetime import datetime

app = Flask(__name__) # 接着我们创建一个该类的实例。第一个参数是应用模块或者包的名称。 __name__ 是一个适用于大多数情况的快捷方式。有了这个参数， Flask 才能知道在哪里可以找到模板和静态文件等东西。

@app.route("/") # 这个装饰器告诉 Flask 哪个 URL 应该触发我们的 hello_world() 函数。这里的 "/" 是根 URL。
def Index(): # 这是一个视图函数。Flask 会在接收到请求时调用这个函数。
    return "<p>index</p>" # 函数返回需要在用户浏览器中显示的信息。默认的内容类型是 HTML ，因此 字符串中的 HTML 会被浏览器渲染。

@app.route("/Hello") 
def hello_world():
    return "<p>Hello World!</p>"

if __name__ == '__main__':
    current_time = datetime.now()

    app.run(host='0.0.0.0', port=5000, debug=True)