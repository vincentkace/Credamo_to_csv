import csv, json, re, requests, threading, tkinter as tk
from tkinter import scrolledtext, messagebox, ttk
from datetime import datetime

requests.packages.urllib3.disable_warnings()

FIELD_NAME_MAP = {
    "answerSign": "答案ID",
    "userSign": "用户ID",
    "answerStartTime": "开始时间",
    "answerEndTime": "结束时间",
    "answerTime": "耗时(秒)",
    "sourceType": "答题渠道",
    "dispenseId": "发布ID",
    "dispenseName": "发布名称",
    "fromIp": "IP地址",
    "lng": "经度",
    "lat": "纬度",
    "country": "国家",
    "province": "省份",
    "city": "城市",
    "deviceType": "设备类型",
    "osType": "操作系统",
    "browserType": "浏览器",
    "resolution": "屏幕分辨率",
    "randomElements": "随机元素",
    "userId": "用户ID",
    "answerId": "答案ID",
    "status": "状态",
}

def parse_cookies(text):
    cookies = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.lower().startswith('name'):
            continue
        if '\t' in line:
            parts = line.split('\t')
            if len(parts) >= 2:
                name, val = parts[0].strip(), parts[1].strip()
                if name and val:
                    cookies[name] = val
        elif '=' in line and ':' not in line.split('=')[0]:
            k, v = line.split('=', 1)
            if k.strip() and v.strip():
                cookies[k.strip()] = v.strip()
    return cookies

def get_field_name(h):
    field_id = h.get("id", "")
    question_name = h.get("questionName", "")
    
    if field_id in FIELD_NAME_MAP:
        return FIELD_NAME_MAP[field_id]
    if question_name:
        return question_name
    return field_id

def download_worker(headers, sid, log_callback):
    all_data, page, total = [], 1, 0
    base_url = "https://www.credamo.com/v1/cleanVar/dataOverview"
    
    log_callback(f"🚀 开始请求问卷 {sid}")
    
    while True:
        try:
            log_callback(f"📥 正在拉取第 {page} 页...")
            r = requests.post(
                base_url,
                headers=headers,
                params={"currPageSize": 200, "currPageIndex": page},
                json={"surveyId": sid},
                timeout=30,
                verify=False
            )
            log_callback(f"  状态码: {r.status_code}")
            
            if r.status_code == 200:
                try:
                    resp_data = r.json()
                except json.JSONDecodeError:
                    log_callback(f"❌ 响应不是JSON: {r.text[:150]}")
                    break
                    
                if resp_data.get("success") and resp_data.get("data"):
                    rows = resp_data["data"].get("rowList", [])
                    all_data.append(resp_data["data"])
                    total += len(rows)
                    log_callback(f"✅ 第{page}页: {len(rows)}条 (累计:{total})")
                    
                    if len(rows) < 200:
                        log_callback("🏁 数据拉取完毕")
                        break
                    page += 1
                else:
                    log_callback(f"❌ 业务错误: {resp_data.get('msg', '未知')}")
                    break
            elif r.status_code == 401:
                log_callback("❌ 401 未授权: Cookie已过期或无效")
                break
            else:
                log_callback(f"❌ HTTP错误: {r.status_code}")
                break
        except requests.exceptions.Timeout:
            log_callback("❌ 请求超时: 网络慢或服务器无响应")
            break
        except Exception as e:
            log_callback(f"❌ 请求异常: {str(e)}")
            break

    return all_data

def save_csv(data, filename, log_callback):
    if not data:
        log_callback("❌ 无数据可保存")
        return False
    
    try:
        header_info = data[0].get("header", [])
        cols = ["userId", "answerId", "status"] + [get_field_name(h) for h in header_info]
        
        with open(filename, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(cols)
            for d in data:
                for row in d.get("rowList", []):
                    row_data = [row.get("userId", ""), row.get("answerId", ""), row.get("status", "")]
                    for h in header_info:
                        row_data.append(row.get(h.get("id", ""), ""))
                    writer.writerow(row_data)
                    
        log_callback(f"💾 已保存: {filename}")
        return True
    except Exception as e:
        log_callback(f"❌ 保存失败: {str(e)}")
        return False

def run():
    cookie_text = txt_cookie.get("1.0", tk.END).strip()
    survey_id = entry_id.get().strip()
    
    log.config(state='normal')
    log.delete("1.0", tk.END)
    log.config(state='disabled')
    
    def log_msg(msg):
        def _update():
            log.config(state='normal')
            timestamp = datetime.now().strftime("%H:%M:%S")
            log.insert(tk.END, f"[{timestamp}] {msg}\n")
            log.see(tk.END)
            log.config(state='disabled')
        root.after(0, _update)

    if not cookie_text:
        messagebox.showwarning("⚠️", "请先粘贴 Cookie 内容")
        return
    if not survey_id or not survey_id.isdigit():
        messagebox.showwarning("⚠️", "请输入有效的问卷ID（纯数字）")
        entry_id.focus()
        return
    
    log_msg("🔍 开始解析Cookie...")
    cookies = parse_cookies(cookie_text)
    
    if not cookies:
        log_msg("❌ 未解析到任何Cookie，请检查粘贴内容")
        messagebox.showerror("❌", "Cookie解析失败")
        return
    
    headers = {
        'cookie': '; '.join(f'{k}={v}' for k, v in cookies.items()),
        'content-type': 'application/json',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    log_msg(f"✅ 解析到 {len(cookies)} 个Cookie")
    log_msg(f"📏 Cookie长度: {len(headers['cookie'])} 字符")
    log_msg(f"🎯 问卷ID: {survey_id}")
    log_msg("🚀 开始下载...")
    
    progress.start(10)
    btn.config(state='disabled', text='下载中...')
    
    def task():
        try:
            data = download_worker(headers, survey_id, log_msg)
            
            if data:
                filename = f"credamo_{survey_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                log_msg("💾 正在保存CSV...")
                if save_csv(data, filename, log_msg):
                    total = sum(len(d.get("rowList", [])) for d in data)
                    log_msg(f"✅ 成功！共下载 {total} 条数据")
                    root.after(0, lambda: messagebox.showinfo("✅ 成功", f"下载完成！\n\n📁 {filename}\n📊 共 {total} 条数据"))
                else:
                    log_msg("❌ 保存文件失败")
            else:
                log_msg("❌ 未获取到任何数据")
                root.after(0, lambda: messagebox.showwarning("⚠️ 提示", "未获取到数据\n\n可能原因：\n1. Cookie已过期（请重新复制）\n2. 问卷ID错误或无权限\n3. 问卷本身暂无数据"))
                
        except Exception as e:
            log_msg(f"❌ 程序异常: {str(e)}")
            root.after(0, lambda: messagebox.showerror("❌ 错误", f"发生未知错误:\n{str(e)}"))
        finally:
            root.after(0, cleanup)
    
    threading.Thread(target=task, daemon=True).start()

def cleanup():
    progress.stop()
    btn.config(state='normal', text='🚀 下载')

root = tk.Tk()
root.title("Credamo 数据下载工具")
root.geometry("700x650")

tk.Label(root, text="📋 步骤：F12→Application→Cookies→全选(Ctrl+A)→复制→粘贴下方→输入问卷ID→点下载", 
         bg="#e3f2fd", pady=8, font=("Microsoft YaHei", 9)).pack(fill=tk.X)

tk.Label(root, text="粘贴 Cookie 内容:", font=("Microsoft YaHei", 9, "bold")).pack(anchor="w", padx=10, pady=(10,5))
txt_cookie = scrolledtext.ScrolledText(root, height=8, font=("Consolas", 9))
txt_cookie.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

id_frame = tk.Frame(root)
id_frame.pack(fill=tk.X, padx=10, pady=5)
tk.Label(id_frame, text="问卷ID:", font=("Microsoft YaHei", 10)).pack(side=tk.LEFT, padx=(0,10))
entry_id = tk.Entry(id_frame, font=("Microsoft YaHei", 10), width=20)
entry_id.pack(side=tk.LEFT)
entry_id.insert(0, "31273164362")
tk.Label(id_frame, text="（纯数字）", fg="gray").pack(side=tk.LEFT, padx=(10,0))

btn = tk.Button(root, text="🚀 下载", command=run, bg="#4CAF50", fg="white", 
                font=("Microsoft YaHei", 12, "bold"), pady=10)
btn.pack(fill=tk.X, padx=10, pady=10)

tk.Label(root, text="进度:", font=("Microsoft YaHei", 9)).pack(anchor="w", padx=10)
progress = ttk.Progressbar(root, mode='indeterminate', length=400)
progress.pack(fill=tk.X, padx=10, pady=5)

tk.Label(root, text="运行日志:", font=("Microsoft YaHei", 9, "bold")).pack(anchor="w", padx=10, pady=(10,5))
log = scrolledtext.ScrolledText(root, height=12, font=("Consolas", 8), state='disabled', bg="#f5f5f5")
log.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

root.mainloop()