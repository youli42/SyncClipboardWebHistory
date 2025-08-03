import subprocess
import sys
import time  # 导入time模块用于延迟

# 启动第一个脚本，不等待其结束
subprocess.Popen([sys.executable, "history_service.py"])

# 延迟2秒
time.sleep(2)

# 2秒后启动第二个脚本
subprocess.run([sys.executable, "web_server.py"])
