r"""
Credamo 批量处理工具 (Playwright版)
使用方式：
1. 先启动Chrome:
   "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --disable-blink-features=AutomationControlled --disable-infobars --user-data-dir="C:\Users\k8723\work\CredamoDataDownloader\Credamo_to_csv\browser_data"

2. 在Chrome中登录Credamo并打开项目

3. 运行此脚本:
   python credamo_playwright.py
"""

from playwright.sync_api import sync_playwright
import tkinter as tk
import time
import pandas as pd
import requests
import json

ANTI_DEBUG_SCRIPT = """
(() => {
    Function.prototype.constructor = function(code){
        if(typeof code === 'string' && code.includes('debugger')){
            code = code.replace(/debugger/g,'');
        }
        return Function.prototype.constructor.call(this, code);
    };

    window.eval = function(code){
        if(typeof code === 'string' && code.includes('debugger')){
            code = code.replace(/debugger/g,'');
        }
        return window.eval(code);
    };

    const rawSetInterval = window.setInterval;
    window.setInterval = function(fn, t){
        const s = fn && fn.toString ? fn.toString() : '';
        if(s.includes('debugger') || s.includes('about:blank') || s.includes('performance.now')){
            return 0;
        }
        return rawSetInterval(fn, t);
    };

    const rawSetTimeout = window.setTimeout;
    window.setTimeout = function(fn, t){
        const s = fn && fn.toString ? fn.toString() : '';
        if(s.includes('debugger')){
            return 0;
        }
        return rawSetTimeout(fn, t);
    };

    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(window, 'outerWidth', { get(){ return window.innerWidth; } });
    Object.defineProperty(window, 'outerHeight', { get(){ return window.innerWidth; } });
    console.clear = function(){};
})();
"""

def get_cookies(context):
    cookies = context.cookies()
    return "; ".join([f"{c['name']}={c['value']}" for c in cookies])

def get_current_page(context, current_page):
    """获取当前聚焦的Credamo页面"""
    all_pages = context.pages
    for pg in all_pages:
        if "credamo.com" in pg.url:
            try:
                if pg.evaluate("() => document.visibilityState === 'visible'") == 'visible':
                    return pg
            except:
                pass
    for pg in all_pages:
        if "credamo.com" in pg.url:
            return pg
    return current_page

def get_survey_id(page):
    """从URL获取surveyId"""
    url = page.url
    try:
        if "surveyId=" in url:
            start = url.index("surveyId=") + len("surveyId=")
            end_chars = ['#', '?', '&']
            end = len(url)
            for c in end_chars:
                pos = url.find(c, start)
                if pos != -1 and pos < end:
                    end = pos
            return int(url[start:end])
    except:
        pass
    return None

def get_page_df(cookie_str, survey_id, page_size, page_num):
    """获取单页数据"""
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "cookie": cookie_str,
        "content-type": "application/json"
    }
    url = "https://www.credamo.com/v1/cleanVar/dataOverview"

    try:
        resp = requests.post(
            url, headers=headers,
            params={"currPageSize": page_size, "currPageIndex": page_num},
            json={"surveyId": survey_id},
            verify=False
        )
        if resp.status_code == 200:
            output = resp.json()
            if output.get("success") and output.get("data"):
                data = output['data']
                return pd.DataFrame(data.get('rowList', [])), data.get('total', 0), data.get('header', [])
        return pd.DataFrame(), 0, []
    except Exception as e:
        print(f"API error: {e}")
        return pd.DataFrame(), 0, []

def download_all_data(cookie_str, survey_id):
    """下载所有数据"""
    # 先用200获取总数
    df, total, headers = get_page_df(cookie_str, survey_id, 200, 1)
    if total == 0:
        total = len(df)

    all_dfs = [df]

    if total > 200:
        page_size = 200
        total_page = (total + page_size - 1) // page_size
        for p in range(2, total_page + 1):
            df, _, _ = get_page_df(cookie_str, survey_id, page_size, p)
            if len(df) > 0:
                all_dfs.append(df)

    result = pd.concat(all_dfs, ignore_index=True)

    # 构建列名映射
    header_map = {}
    for h in headers:
        header_id = h.get('id', '')
        q_num = h.get('qNum', '')
        q_name = h.get('questionName', '')
        if q_num and q_name:
            header_map[header_id] = f"{q_num} {q_name}"
        elif q_name:
            header_map[header_id] = q_name

    # 替换列名
    result.columns = [header_map.get(c, c) if c not in ['status', 'answerId', 'userId'] else c for c in result.columns]

    # 剔除已拒绝的
    result = result[(result == "*").sum(axis=1) == 0]

    return result

def go_to_data_clean(page):
    """确保在数据清理页面"""
    try:
        page.locator(".iconfont.icon-shaixuan").wait_for(timeout=2000)
        return
    except:
        pass
    try:
        page.locator("text=数据清理").click()
        time.sleep(2)
    except:
        pass

def set_page_size(page, size=10):
    """设置每页条数"""
    try:
        page.locator('.el-input__inner').first.click()
        time.sleep(1)
        page.locator(f'.el-select-dropdown__item >> nth={size//10 - 1 if size in [10,20,30,40,50] else 0}').click()
        time.sleep(1)
    except:
        pass

def go_to_page(page, num):
    """跳转到指定页"""
    try:
        page.locator('.el-pagination__jump .el-input__inner').fill(str(num))
        page.locator('.el-pagination__jump .el-input__inner').press('Enter')
        time.sleep(1)
    except:
        pass

def select_user(page, row_idx):
    """勾选用户"""
    try:
        page.locator(f'table tbody tr:nth-child({row_idx}) td:first-child span').first.click()
        time.sleep(0.2)
    except:
        pass

def batch_reject(page, auto=True):
    """批量拒绝"""
    try:
        page.locator('.el-dropdown').click()
        time.sleep(1)
        page.locator('.el-dropdown-menu__item').nth(1).click()
        time.sleep(2)

        if auto:
            try:
                page.locator('.el-select').first.click()
                time.sleep(1)
                page.locator('.el-select-dropdown__item:has-text("填写内容不符合要求")').click()
                time.sleep(1)
                page.locator('button:has-text("批量拒绝")').click()
                time.sleep(3)
            except:
                try:
                    page.locator('button:has-text("确定")').click()
                except:
                    pass
    except:
        pass

def batch_accept(page, auto=True):
    """批量接受"""
    try:
        page.locator('.el-dropdown').click()
        time.sleep(1)
        page.locator('.el-dropdown-menu__item').nth(0).click()
        time.sleep(2)

        if auto:
            try:
                page.locator('button:has-text("确定")').first.click()
                time.sleep(2)
            except:
                pass
    except:
        pass

def main():
    # 连接Chrome
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.new_page()
        page.add_init_script(ANTI_DEBUG_SCRIPT)

        # 获取当前页面
        page = get_current_page(context, page)

        # 创建GUI
        root = tk.Tk()
        root.title("Credamo批量处理 (Playwright版)")
        root.geometry("600x500")

        info_text = tk.Text(root, height=12)
        info_text.pack(fill="both", expand=True, padx=10, pady=5)

        def show(msg):
            info_text.insert("0.0", f"\n{msg}")

        show("请在Chrome中打开项目页面，然后点击操作按钮")

        user_ids_text = tk.Text(root, height=8)
        user_ids_text.pack(fill="x", padx=10, pady=5)
        tk.Label(root, text="粘贴待拒绝的用户ID（每行一个）").pack()

        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=10)

        def do_download():
            page = get_current_page(context, page)
            survey_id = get_survey_id(page)
            if not survey_id:
                show("无法获取项目ID，请在Chrome中打开项目")
                return

            show("正在下载...")
            cookie_str = get_cookies(context)

            try:
                df = download_all_data(cookie_str, survey_id)
                filename = f"credamo_{survey_id}_{time.strftime('%Y%m%d_%H%M%S')}.csv"
                df.to_csv(filename, index=False, encoding='utf-8-sig')
                show(f"已保存到 {filename}，共 {len(df)} 条数据")
            except Exception as e:
                show(f"下载失败: {e}")

        def do_reject():
            page = get_current_page(context, page)
            survey_id = get_survey_id(page)
            if not survey_id:
                show("无法获取项目ID")
                return

            go_to_data_clean(page)
            set_page_size(page, 10)

            reject_ids = [uid.strip() for uid in user_ids_text.get("0.0", "end").strip().split('\n') if uid.strip()]
            if not reject_ids:
                show("请先输入待拒绝的用户ID")
                return

            cookie_str = get_cookies(context)
            df, total, _ = get_page_df(cookie_str, survey_id, 10, 1)
            total_page = (total + 9) // 10

            show(f"开始拒绝，共 {total_page} 页...")

            for pnum in range(1, total_page + 1):
                go_to_page(page, pnum)
                time.sleep(2)

                df, _, _ = get_page_df(cookie_str, survey_id, 10, pnum)
                if 'userId' not in df.columns:
                    continue

                page_ids = df['userId'].tolist()
                to_reject = list(set(reject_ids) & set(page_ids))

                for uid in to_reject:
                    idx = page_ids.index(uid) + 1
                    select_user(page, idx)

                if to_reject:
                    batch_reject(page, auto=True)
                    show(f"第{pnum}页已拒绝 {len(to_reject)} 个")

            show("批量拒绝完成")

        def do_accept():
            page = get_current_page(context, page)
            survey_id = get_survey_id(page)
            if not survey_id:
                show("无法获取项目ID")
                return

            go_to_data_clean(page)
            set_page_size(page, 10)

            reject_ids = [uid.strip() for uid in user_ids_text.get("0.0", "end").strip().split('\n') if uid.strip()]

            cookie_str = get_cookies(context)
            df, total, _ = get_page_df(cookie_str, survey_id, 10, 1)
            total_page = (total + 9) // 10

            show(f"开始接受，共 {total_page} 页...")

            for pnum in range(1, total_page + 1):
                go_to_page(page, pnum)
                time.sleep(2)

                df, _, _ = get_page_df(cookie_str, survey_id, 10, pnum)
                if 'userId' not in df.columns:
                    continue

                # 接受不在拒绝列表中的
                page_ids = df['userId'].tolist()
                to_accept = [uid for uid in page_ids if uid not in reject_ids]

                for i, uid in enumerate(to_accept, 1):
                    select_user(page, i)

                if to_accept:
                    batch_accept(page, auto=True)
                    show(f"第{pnum}页已接受 {len(to_accept)} 个")

            show("批量接受完成")

        def do_manual():
            page = get_current_page(context, page)
            survey_id = get_survey_id(page)
            if not survey_id:
                show("无法获取项目ID")
                return

            go_to_data_clean(page)
            set_page_size(page, 10)

            reject_ids = [uid.strip() for uid in user_ids_text.get("0.0", "end").strip().split('\n') if uid.strip()]

            cookie_str = get_cookies(context)
            df, _, _ = get_page_df(cookie_str, survey_id, 10, 1)

            if 'userId' not in df.columns:
                show("无数据")
                return

            page_ids = df['userId'].tolist()
            to_select = list(set(reject_ids) & set(page_ids))

            for uid in to_select:
                idx = page_ids.index(uid) + 1
                select_user(page, idx)

            show(f"已选中 {len(to_select)} 个，请在浏览器中手动确认")

        tk.Button(btn_frame, text="下载数据", command=do_download, width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="自动拒绝", command=do_reject, width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="自动接受剩余", command=do_accept, width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="手动拒绝", command=do_manual, width=12).pack(side="left", padx=5)

        root.mainloop()

if __name__ == "__main__":
    main()