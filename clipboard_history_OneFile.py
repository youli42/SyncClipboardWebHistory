import os
import json
import time
import shutil
import html
import hashlib
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# 配置路径（根据实际环境修改）
SYNC_FILE = "SyncClipboard.json"  # 主同步文件路径
HISTORY_FILE = "clipboard_history.json"  # 历史记录文件
HISTORY_IMAGES_DIR = "history_images"  # 历史图片存储目录
FILE_DIR = "file"  # 原始图片存储目录
HTML_FILE = "clipboard_history.html"  # 生成的网页文件
HISTORY_FILES_DIR = "history_files"  # 新增历史文件夹

os.makedirs(HISTORY_IMAGES_DIR, exist_ok=True)
os.makedirs(HISTORY_FILES_DIR, exist_ok=True)

def file_md5(path):
    hash_md5 = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

class ClipboardHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_content = None

    def on_modified(self, event):
        if os.path.basename(event.src_path) == SYNC_FILE:
            self.process_clipboard()

    def process_clipboard(self):
        try:
            with open(SYNC_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if not content or content == self.last_content:
                return
            self.last_content = content
            data = json.loads(content)
            timestamp = datetime.now().isoformat()

            # 备份图片或文件
            if data["Type"] in ("Image", "File") and data["File"]:
                src_path = os.path.join(FILE_DIR, data["File"])
                dst_path = os.path.join(HISTORY_FILES_DIR, data["File"])
                history_file = data["File"]
                if os.path.exists(src_path):
                    # 判断是否已存在且内容相同
                    if os.path.exists(dst_path):
                        if file_md5(src_path) == file_md5(dst_path):
                            # 内容相同，直接用原有文件名
                            history_file = data["File"]
                        else:
                            # 内容不同，重命名备份
                            name, ext = os.path.splitext(data["File"])
                            new_name = f"{name}_{int(time.time())}{ext}"
                            dst_path = os.path.join(HISTORY_FILES_DIR, new_name)
                            shutil.copy2(src_path, dst_path)
                            history_file = new_name
                    else:
                        shutil.copy2(src_path, dst_path)
                        history_file = data["File"]
                data["HistoryFile"] = history_file  # 关键：每次都赋值
            # 添加到历史记录
            history_entry = {
                "timestamp": timestamp,
                "data": data
            }
            self.save_to_history(history_entry)
            self.generate_html()
        except Exception as e:
            print(f"处理错误: {str(e)}")

    def save_to_history(self, entry):
        history = []
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except:
                pass
                
        history.append(entry)
        
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

    def generate_html(self):
        if not os.path.exists(HISTORY_FILE):
            return
            
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
        
        history.reverse()
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <title>剪贴板历史记录</title>
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
                .entry {{ border: 1px solid #ddd; border-radius: 5px; padding: 15px; margin-bottom: 15px; }}
                .timestamp {{ color: #666; font-size: 0.9em; margin-bottom: 5px; }}
                .text-content {{ white-space: pre-wrap; background-color: #f9f9f9; padding: 10px; border-radius: 4px; }}
                .image-content {{ max-width: 100%; margin-top: 10px; }}
                .type-label {{ display: inline-block; padding: 2px 6px; background: #eee; border-radius: 3px; font-size: 0.8em; }}
                .download-btn {{ display: inline-block; margin-top: 10px; padding: 8px 12px; background: #007bff; color: white; text-decoration: none; border-radius: 4px; }}
                .download-btn:hover {{ background: #0056b3; }}
            </style>
            <!-- 引入 marked.js 用于 Markdown 渲染 -->
            <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
        </head>
        <body>
            <h1>剪贴板历史记录</h1>
            <div id="history">
        """
        
        for idx, entry in enumerate(history):
            data = entry["data"]
            timestamp = datetime.fromisoformat(entry["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
            type_label = f'<span class="type-label">{data["Type"]}</span>'
            content_html = ""
            if data["Type"] == "Text":
                text_content = data["Clipboard"]
                # 简单判断格式
                if text_content.strip().startswith("<") and text_content.strip().endswith(">"):
                    # 可能是 HTML
                    content_html = f'<div class="text-content">{text_content}</div>'
                elif any(sym in text_content for sym in ['#', '*', '-', '`', '[', ']']):
                    # 可能是 Markdown，前端渲染
                    content_html = f'<div class="text-content" id="md-{idx}">{html.escape(text_content)}</div>'
                    content_html += f"""
                    <script>
                    document.getElementById('md-{idx}').innerHTML = marked.parse(document.getElementById('md-{idx}').innerText);
                    </script>
                    """
                else:
                    # 普通文本
                    content_html = f'<div class="text-content">{html.escape(text_content)}</div>'
            elif data["Type"] in ("Image", "File") and data.get("HistoryFile"):
                file_path = os.path.join(HISTORY_FILES_DIR, data["HistoryFile"])
                file_name = os.path.basename(data["HistoryFile"])
                if data["Type"] == "Image":
                    content_html = (
                        f'<img src="{file_path}" class="image-content" alt="剪贴板图片"><br>'
                        f'<a href="{file_path}" download class="download-btn">{file_name} 下载图片</a>'
                    )
                else:
                    content_html = (
                        f'<a href="{file_path}" download class="download-btn">{file_name} 下载文件</a>'
                    )
            
            html_content += f"""
            <div class="entry">
                <div class="timestamp">{timestamp} {type_label}</div>
                {content_html}
            </div>
            """
        
        html_content += """
            </div>
        </body>
        </html>
        """
        
        with open(HTML_FILE, "w", encoding="utf-8") as f:
            f.write(html_content)

def main():
    event_handler = ClipboardHandler()
    observer = Observer()
    observer.schedule(event_handler, path=".", recursive=False)
    observer.start()
    
    print(f"监控已启动，剪贴板历史将保存到: {HISTORY_FILE}")
    print(f"网页界面: {HTML_FILE}")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    # 首次运行生成HTML
    handler = ClipboardHandler()
    handler.generate_html()
    main()