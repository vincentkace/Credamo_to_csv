import tkinter as tk
from tkinter import ttk

def create_gui(callbacks):
    """创建GUI界面

    Args:
        callbacks: 回调函数字典，包含:
            - open_credamo
            - download_data
            - batch_reject
            - batch_accept
            - manual_reject
    """
    window = tk.Tk()
    window.title("Credamo批量处理工具 (Playwright版)")
    window.geometry("600x500")

    # 顶部按钮栏
    top_frame = tk.Frame(window)
    top_frame.pack(pady=10)

    tk.Button(top_frame, text='打开Credamo网站', width=15, height=1,
              command=callbacks['open_credamo']).pack(side="left", padx=5)

    tk.Label(top_frame, text="  ").pack(side="left")

    tk.Button(top_frame, text='下载数据', width=15, height=1,
              command=callbacks['download_data']).pack(side="left", padx=5)

    # 下载文件名输入框
    download_name = tk.Text(top_frame, height=1, width=20)
    download_name.insert("0.0", "credamo_data")
    download_name.pack(side="left", padx=5)

    tk.Label(top_frame, text="_YYYYmmdd_HHMMSS.csv", width=20).pack(side="left")

    # 说明标签
    tk.Label(window, text="请在下面粘贴待拒绝被试的用户ID（每行一个）",
             width=40, height=2).pack()

    # 用户ID输入框
    user_id_text = tk.Text(window, height=10)
    user_id_text.pack(fill="x", padx=20, pady=5)

    # 操作按钮栏
    action_frame = tk.Frame(window)
    action_frame.pack(pady=10)

    tk.Button(action_frame, text='自动拒绝被试', width=12, height=1,
              command=callbacks['batch_reject']).pack(side="left", padx=5)

    tk.Button(action_frame, text='自动接受剩余', width=12, height=1,
              command=callbacks['batch_accept']).pack(side="left", padx=5)

    tk.Label(action_frame, text="  ").pack(side="left")

    tk.Button(action_frame, text='手动拒绝', width=10, height=1,
              command=callbacks['manual_reject']).pack(side="left", padx=5)

    # 页码输入
    tk.Label(action_frame, text="第").pack(side="left")
    page_num_text = tk.Text(action_frame, height=1, width=4)
    page_num_text.insert("0.0", "1")
    page_num_text.pack(side="left")
    tk.Label(action_frame, text="页").pack(side="left")

    # 提示区域
    tk.Label(window, text="----提示信息----", width=30, height=2).pack()

    info_text = tk.Text(window, height=10)
    info_text.pack(fill="both", expand=True, padx=20, pady=5)

    # 初始提示
    info_text.insert("0.0", "欢迎使用Credamo批量处理工具！\n"
                           "1. 点击\"打开Credamo网站\"登录\n"
                           "2. 打开需要处理的项目\n"
                           "3. 粘贴待拒绝的用户ID\n"
                           "4. 点击相应按钮执行操作\n")

    def show_info(message):
        info_text.insert("0.0", f"\n{message}")

    return window, {
        'download_name': download_name,
        'user_id_text': user_id_text,
        'page_num_text': page_num_text,
        'show_info': show_info
    }
