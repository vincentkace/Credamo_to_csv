import time
import os
import sys
import pandas as pd

from browser import launch_browser, get_cookies, is_logged_in
from api import get_page_df, download_all_data
from page_ops import (
    get_survey_id, go_to_data_clean_page, set_page_size,
    go_to_page, select_user, batch_reject, batch_accept
)
from gui import create_gui

def main():
    connect_existing = True

    # if connect_existing:
    #     print("=== 开发者模式：连接已有Chrome ===")
    #     print("请先手动启动Chrome: chrome --remote-debugging-port=9222")
    #     print("然后在Chrome中手动登录Credamo并打开项目\n")
    # else:
    #     print("=== 正常模式：启动新Chrome ===\n")


    # 启动浏览器
    try:
        p, browser, context, page = launch_browser(connect_existing=connect_existing)
    except Exception as e:
        print(e)
        print(r'请先手动启动Chrome(需要修改user data为你电脑的某一个固定的路径): "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --disable-blink-features=AutomationControlled --disable-infobars --user-data-dir="C:\Users\k8723\work\CredamoDataDownloader\Credamo_to_csv\browser_data"')
        print("然后再启动本代码python main.py\n")
        exit()

    if not connect_existing:
        # 只有非连接模式才需要自动打开网站
        # 打开Credamo网站
        page.goto("https://www.credamo.com")
        print("请登录Credamo账号...")

        # 等待用户登录
        while not is_logged_in(context):
            time.sleep(2)

        print("登录成功！")
    else:
        print("已连接到浏览器，当前页面:", page.url)
        if not is_logged_in(context):
            print("请先登录Credamo...")

    # 回调函数
    def open_credamo():
        gui_vars['show_info']("请在浏览器中打开需要处理的项目")
        page.goto("https://www.credamo.com")
        time.sleep(3)

    def download_data():
        # 获取surveyId
        survey_id = get_survey_id(page)
        if not survey_id:
            gui_vars['show_info']("无法获取项目ID，请先打开一个项目")
            return

        gui_vars['show_info']("正在下载数据...")

        # 确保在数据清理页面
        go_to_data_clean_page(page)
        set_page_size(page, 10)

        # 获取cookie
        cookie_str = get_cookies(context)

        # 下载数据
        filename = gui_vars['download_name'].get("0.0", "end").strip()
        filename = f"{filename}_{time.strftime('%Y%m%d_%H%M%S')}.csv"

        try:
            df = download_all_data(cookie_str, survey_id, page_size=10)
            df.to_csv(filename, encoding='utf-8', index=False)
            gui_vars['show_info'](f"数据已保存到: {filename}")
        except Exception as e:
            gui_vars['show_info'](f"下载失败: {e}")

    def batch_reject_auto():
        # 批量拒绝
        gui_vars['show_info']("开始批量拒绝...")
        survey_id = get_survey_id(page)
        if not survey_id:
            gui_vars['show_info']("无法获取项目ID")
            return

        # 设置每页10条
        go_to_data_clean_page(page)
        set_page_size(page, 10)

        # 获取待拒绝的userId列表
        reject_ids = gui_vars['user_id_text'].get("0.0", "end").strip().split('\n')
        reject_ids = [uid.strip() for uid in reject_ids if uid.strip()]

        if not reject_ids:
            gui_vars['show_info']("请先输入待拒绝的用户ID")
            return

        cookie_str = get_cookies(context)

        # 获取第一页数据确定总数
        df, total_cnt = get_page_df(cookie_str, survey_id, 10, 1)
        total_page = total_cnt // 10 + 1

        for page_num in range(1, total_page + 1):
            go_to_page(page, page_num)
            time.sleep(2)

            df, _ = get_page_df(cookie_str, survey_id, 10, page_num)

            if 'userId' not in df.columns:
                continue

            page_user_ids = df['userId'].tolist()
            page_reject_ids = list(set(reject_ids) & set(page_user_ids))

            # 勾选需要拒绝的用户
            for reject_id in page_reject_ids:
                row_idx = page_user_ids.index(reject_id) + 1
                select_user(page, row_idx)
                time.sleep(0.2)

            # 批量拒绝
            if page_reject_ids:
                batch_reject(page, auto=True)
                gui_vars['show_info'](f"第{page_num}页已拒绝{len(page_reject_ids)}个用户")

        gui_vars['show_info']("批量拒绝完成！")

    def batch_accept_auto():
        # 批量接受剩余
        gui_vars['show_info']("开始批量接受...")
        survey_id = get_survey_id(page)
        if not survey_id:
            gui_vars['show_info']("无法获取项目ID")
            return

        go_to_data_clean_page(page)
        set_page_size(page, 10)

        cookie_str = get_cookies(context)

        df, total_cnt = get_page_df(cookie_str, survey_id, 10, 1)
        total_page = total_cnt // 10 + 1

        for page_num in range(1, total_page + 1):
            go_to_page(page, page_num)
            time.sleep(2)

            df, _ = get_page_df(cookie_str, survey_id, 10, page_num)

            if 'userId' not in df.columns:
                continue

            # 获取未拒绝的用户
            page_user_ids = df[df['status'] != '*']['userId'].tolist()

            # 勾选所有用户
            for i, _ in enumerate(page_user_ids, 1):
                select_user(page, i)
                time.sleep(0.2)

            # 批量接受
            if page_user_ids:
                batch_accept(page, auto=True)
                gui_vars['show_info'](f"第{page_num}页已接受{len(page_user_ids)}个用户")

        gui_vars['show_info']("批量接受完成！")

    def manual_reject():
        # 手动拒绝（只选中不自动点确定）
        gui_vars['show_info']("手动拒绝模式：请在浏览器中手动操作")
        survey_id = get_survey_id(page)
        if not survey_id:
            gui_vars['show_info']("无法获取项目ID")
            return

        # 跳转到指定页
        try:
            page_num = int(gui_vars['page_num_text'].get("0.0", "end").strip())
            go_to_page(page, page_num)
            time.sleep(2)
        except:
            gui_vars['show_info']("请输入有效的页码")

        cookie_str = get_cookies(context)

        df, _ = get_page_df(cookie_str, survey_id, 10, page_num)

        if 'userId' not in df.columns:
            gui_vars['show_info']("该页无用户数据")
            return

        reject_ids = gui_vars['user_id_text'].get("0.0", "end").strip().split('\n')
        reject_ids = [uid.strip() for uid in reject_ids if uid.strip()]

        page_user_ids = df['userId'].tolist()
        page_reject_ids = list(set(reject_ids) & set(page_user_ids))

        for reject_id in page_reject_ids:
            row_idx = page_user_ids.index(reject_id) + 1
            select_user(page, row_idx)

        gui_vars['show_info'](f"已选中{len(page_reject_ids)}个用户，请在浏览器中手动点击拒绝")

    # 创建GUI
    window, gui_vars = create_gui({
        'open_credamo': open_credamo,
        'download_data': download_data,
        'batch_reject': batch_reject_auto,
        'batch_accept': batch_accept_auto,
        'manual_reject': manual_reject
    })

    def on_closing():
        # browser.close()
        # p.stop()
        window.destroy()

    window.protocol("WM_DELETE_WINDOW", on_closing)
    window.mainloop()


if __name__ == "__main__":
    main()
