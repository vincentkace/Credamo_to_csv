import time
import os
import sys
import requests
import csv

from browser import (
    launch_browser, get_cookies, is_logged_in, extract_survey_id,
    find_survey_id_via_cdp, get_all_page_urls, get_cdp_pages
)
from api import get_page_df
from page_ops import (
    go_to_data_clean_page, is_data_clean_page, set_page_size,
    go_to_page, select_user, batch_reject, batch_accept
)
from gui import create_gui

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    config = {}
    try:
        from config import load_config
        config = load_config()
    except:
        pass

    cdp_port = config.get("cdp_port", 9222)

    print("正在启动浏览器...")
    try:
        p, browser, context, page, survey_id = launch_browser()
    except Exception as e:
        print(e)
        print("启动浏览器失败，请检查配置")
        input("按回车键退出...")
        sys.exit(1)

    print("已连接到浏览器，当前页面:", page.url)
    if survey_id:
        print(f"检测到问卷ID: {survey_id}")

    logged_in = is_logged_in(context)
    all_urls = get_all_page_urls(browser, cdp_port)
    has_credamo = any("credamo.com" in url for url in all_urls)

    if not has_credamo or not logged_in:
        print("正在打开Credamo网站...")
        page.goto("https://www.credamo.com")
        time.sleep(3)
        logged_in = is_logged_in(context)

    print(f"登录状态: {logged_in}")

    def get_survey_id_dynamic():
        """动态获取survey_id，通过CDP实时接口遍历所有页面"""
        sid, target_id, url = find_survey_id_via_cdp(cdp_port)
        if sid:
            print(f"找到问卷ID: {sid} (URL: {url})")
            return sid
        return None

    def ensure_data_clean_page(survey_id):
        """确保页面在dataClean页面，如果不在则先跳转

        SPA使用hash路由，page.goto()只改hash不会触发Vue路由重渲染，
        需要通过JS修改hash或点击侧边栏导航
        """
        current_url = page.url

        if "#/dataClean" in current_url and f"surveyId={survey_id}" in current_url:
            if _wait_for_data_clean(page, timeout=3000):
                return True

        # 策略1: 如果已在同surveyId页面，用JS修改hash触发Vue路由
        if f"surveyId={survey_id}" in current_url:
            print(f"同项目不同页面({current_url})，通过JS修改hash跳转到dataClean")
            try:
                page.evaluate("window.location.hash = '#/dataClean'")
                if _wait_for_data_clean(page, timeout=8000):
                    return True
            except Exception as e:
                print(f"JS hash跳转失败: {e}")

        # 策略2: 完整URL导航（不在该项目页面时）
        target_url = f"https://www.credamo.com/survey.html?surveyId={survey_id}#/dataClean"
        print(f"尝试完整URL跳转: {target_url}")
        try:
            page.goto(target_url, wait_until="domcontentloaded")
            time.sleep(2)
            if _wait_for_data_clean(page, timeout=10000):
                return True
        except Exception as e:
            print(f"URL跳转失败: {e}")

        # 策略3: 点击侧边栏"数据"菜单项
        try:
            nav_items = page.locator(".el-menu-item, .nav-item, [class*='menu']").all()
            for item in nav_items:
                text = item.text_content().strip() if item.is_visible() else ""
                if "数据" in text or "清理" in text:
                    item.click()
                    time.sleep(2)
                    if _wait_for_data_clean(page, timeout=5000):
                        return True
        except Exception as e:
            print(f"点击导航失败: {e}")

        gui_vars['show_info']("无法自动跳转到数据清理页面，请手动点击左侧'数据'菜单")
        return False

    def _wait_for_data_clean(page_obj, timeout=8000):
        """等待数据清理页面加载完成"""
        try:
            page_obj.locator("table tbody tr").first.wait_for(timeout=timeout)
            page_obj.locator(".el-pagination").wait_for(timeout=3000)
            print("数据清理页面已加载")
            return True
        except:
            pass
        try:
            page_obj.locator(".iconfont.icon-shaixuan").wait_for(timeout=3000)
            print("数据清理页面已加载（通过筛选图标确认）")
            return True
        except:
            pass
        return False

    def open_credamo():
        gui_vars['show_info']("请在浏览器中打开需要处理的项目")
        page.goto("https://www.credamo.com")
        time.sleep(3)

    def download_data():
        survey_id = get_survey_id_dynamic()

        if not survey_id:
            all_urls = get_all_page_urls(browser, cdp_port)
            gui_vars['show_info']("无法获取项目ID，请先打开一个项目")
            gui_vars['show_info'](f"当前URLs: {all_urls}")
            return

        gui_vars['show_info']("正在下载数据...")
        gui_vars['set_progress'](10)

        cookie_str = get_cookies(context)

        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "referer": f"https://www.credamo.com/survey.html?surveyId={survey_id}",
            "cookie": cookie_str,
            "content-type": "application/json"
        }

        all_data = []
        page_num = 1
        total = 0
        base_url = "https://www.credamo.com/v1/cleanVar/dataOverview"

        gui_vars['show_info']("开始下载...")

        while True:
            try:
                r = requests.post(
                    base_url,
                    headers=headers,
                    params={"currPageSize": 200, "currPageIndex": page_num},
                    json={"surveyId": survey_id},
                    timeout=30,
                    verify=False
                )

                if r.status_code == 200:
                    resp_data = r.json()
                    if resp_data.get("success") and resp_data.get("data"):
                        rows = resp_data["data"].get("rowList", [])
                        all_data.append(resp_data["data"])
                        total += len(rows)
                        gui_vars['show_info'](f"第{page_num}页: {len(rows)}条 (累计: {total})")

                        if len(rows) < 200:
                            gui_vars['show_info']("数据下载完毕")
                            break
                        page_num += 1
                    else:
                        gui_vars['show_info'](f"下载失败: {resp_data.get('msg', '未知错误')}")
                        break
                else:
                    gui_vars['show_info']("下载失败")
                    break
            except Exception as e:
                gui_vars['show_info']("请求异常")
                break

        if not all_data:
            gui_vars['show_info']("无数据可保存")
            return

        gui_vars['show_info']("正在保存CSV...")
        gui_vars['set_progress'](80)

        filename = gui_vars['download_name'].get("0.0", "end").strip()
        filename = f"{filename}_{time.strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = os.path.join(OUTPUT_DIR, filename)

        try:
            header_info = all_data[0].get("header", [])
            cols = ["userId", "answerId", "status"] + [h.get("questionName", "") or h.get("id", "") for h in header_info]

            with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(cols)
                for d in all_data:
                    for row in d.get("rowList", []):
                        row_values = list(row.values())
                        if "*" in row_values:
                            continue
                        row_data = [row.get("userId", ""), row.get("answerId", ""), row.get("status", "")]
                        for h in header_info:
                            row_data.append(row.get(h.get("id", ""), ""))
                        writer.writerow(row_data)

            gui_vars['show_info'](f"已保存: {filepath}")
            gui_vars['set_progress'](100)
        except Exception as e:
            gui_vars['show_info']("保存失败")

    def batch_reject_auto():
        gui_vars['show_info']("开始批量拒绝...")
        survey_id = get_survey_id_dynamic()
        if not survey_id:
            gui_vars['show_info']("无法获取项目ID")
            return

        if not ensure_data_clean_page(survey_id):
            gui_vars['show_info']("无法跳转到数据清理页面")
            return
        set_page_size(page, 10)

        reject_ids_raw = gui_vars['user_id_text'].get("0.0", "end").strip().split('\n')
        reject_ids = set()
        for uid in reject_ids_raw:
            uid = uid.strip()
            if uid:
                reject_ids.add(uid)

        if not reject_ids:
            gui_vars['show_info']("请先输入待拒绝的用户ID")
            return

        cookie_str = get_cookies(context)
        total_rejected = 0

        current_page = 1

        while reject_ids:
            df, total_cnt = get_page_df(cookie_str, survey_id, 10, current_page)

            if 'userId' not in df.columns or df.empty:
                break

            page_user_ids = df['userId'].tolist()
            page_reject_ids = list(reject_ids & set(page_user_ids))

            if page_reject_ids:
                go_to_page(page, current_page)
                time.sleep(2)

                df, _ = get_page_df(cookie_str, survey_id, 10, current_page)
                if 'userId' not in df.columns or df.empty:
                    break
                page_user_ids = df['userId'].tolist()
                page_reject_ids = list(reject_ids & set(page_user_ids))

                if page_reject_ids:
                    for reject_id in page_reject_ids:
                        if reject_id in page_user_ids:
                            row_idx = page_user_ids.index(reject_id) + 1
                            select_user(page, row_idx)
                            time.sleep(0.3)

                    batch_reject(page, auto=True)
                    reject_ids -= set(page_reject_ids)
                    total_rejected += len(page_reject_ids)
                    gui_vars['show_info'](f"第{current_page}页已拒绝{len(page_reject_ids)}个用户 (累计: {total_rejected}, 剩余待拒绝: {len(reject_ids)})")
                    time.sleep(2)
                    continue

            if len(df) < 10:
                break

            current_page += 1

        gui_vars['show_info'](f"批量拒绝完成！共拒绝{total_rejected}个用户" + (f"，{len(reject_ids)}个未找到" if reject_ids else ""))

    def batch_accept_auto():
        gui_vars['show_info']("开始批量接受...")
        survey_id = get_survey_id_dynamic()
        if not survey_id:
            gui_vars['show_info']("无法获取项目ID")
            return

        if not ensure_data_clean_page(survey_id):
            gui_vars['show_info']("无法跳转到数据清理页面")
            return
        set_page_size(page, 10)

        cookie_str = get_cookies(context)
        total_accepted = 0

        current_page = 1
        max_page = 9999
        empty_streak = 0

        while current_page <= max_page and empty_streak < 3:
            df, total_cnt = get_page_df(cookie_str, survey_id, 10, current_page)

            if total_cnt > 0:
                max_page = (total_cnt + 9) // 10

            if 'userId' not in df.columns or df.empty:
                empty_streak += 1
                if current_page >= max_page:
                    break
                current_page += 1
                continue

            page_user_ids = df['userId'].tolist()
            accept_user_ids = df[df['status'] == 1]['userId'].tolist()
            reject_ids_raw = gui_vars['user_id_text'].get("0.0", "end").strip().split('\n')
            reject_ids = set()
            for uid in reject_ids_raw:
                uid = uid.strip()
                if uid:
                    reject_ids.add(uid)
            accept_user_ids = [uid for uid in accept_user_ids if uid not in reject_ids]

            if not accept_user_ids:
                empty_streak += 1
                if current_page >= max_page:
                    break
                current_page += 1
                go_to_page(page, current_page)
                time.sleep(2)
                continue

            empty_streak = 0

            go_to_page(page, current_page)
            time.sleep(2)

            df, _ = get_page_df(cookie_str, survey_id, 10, current_page)
            if 'userId' not in df.columns or df.empty:
                continue
            page_user_ids = df['userId'].tolist()
            accept_user_ids = df[df['status'] == 1]['userId'].tolist()
            accept_user_ids = [uid for uid in accept_user_ids if uid not in reject_ids]

            if not accept_user_ids:
                continue

            for uid in accept_user_ids:
                row_idx = page_user_ids.index(uid) + 1
                select_user(page, row_idx)
                time.sleep(0.3)

            batch_accept(page, auto=True)
            total_accepted += len(accept_user_ids)
            gui_vars['show_info'](f"第{current_page}页已接受{len(accept_user_ids)}个用户 (累计: {total_accepted})")

            time.sleep(2)
            current_page += 1
            go_to_page(page, current_page)
            time.sleep(2)

        gui_vars['show_info'](f"批量接受完成！共接受{total_accepted}个用户")

    def manual_reject():
        gui_vars['show_info']("手动拒绝模式：请在浏览器中手动操作")
        survey_id = get_survey_id_dynamic()
        if not survey_id:
            gui_vars['show_info']("无法获取项目ID")
            return

        if not ensure_data_clean_page(survey_id):
            gui_vars['show_info']("无法跳转到数据清理页面")
            return

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

        reject_ids_raw = gui_vars['user_id_text'].get("0.0", "end").strip().split('\n')
        reject_ids = set()
        for uid in reject_ids_raw:
            uid = uid.strip()
            if uid:
                reject_ids.add(uid)

        page_user_ids = df['userId'].tolist()
        page_reject_ids = list(reject_ids & set(page_user_ids))

        for reject_id in page_reject_ids:
            row_idx = page_user_ids.index(reject_id) + 1
            select_user(page, row_idx)

        gui_vars['show_info'](f"已选中{len(page_reject_ids)}个用户，请在浏览器中手动点击拒绝")

    window, gui_vars = create_gui({
        'open_credamo': open_credamo,
        'download_data': download_data,
        'batch_reject': batch_reject_auto,
        'batch_accept': batch_accept_auto,
        'manual_reject': manual_reject
    })

    def on_closing():
        window.destroy()

    window.protocol("WM_DELETE_WINDOW", on_closing)
    window.mainloop()


if __name__ == "__main__":
    main()
