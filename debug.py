"""
Credamo 调试脚本
用于测试各个模块功能
"""
import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(__file__))

# 设置输出编码
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from browser import launch_browser, get_cookies, is_logged_in
from page_ops import get_survey_id
from api import get_page_df, download_all_data, save_to_file
import time

def test_browser():
    """测试浏览器连接"""
    print("\n=== Test 1: Browser Connection ===")
    p, browser, context, page = launch_browser(connect_existing=True)

    print(f"Current URL: {page.url}")
    print(f"Page title: {page.title()}")

    # 检查登录状态
    if is_logged_in(context):
        print("[OK] Already logged in")
    else:
        print("[X] Not logged in")

    return p, browser, context, page

def test_survey_id(page):
    """测试获取surveyId"""
    print("\n=== Test 2: Get SurveyId ===")

    url = page.url
    print(f"URL: {repr(url)}")

    if "surveyId=" in url:
        start_loc = url.index("surveyId=") + len("surveyId=")
        end_chars = ['#', '?', '&']
        end_loc = len(url)
        for char in end_chars:
            pos = url.find(char, start_loc)
            if pos != -1 and pos < end_loc:
                end_loc = pos

        survey_id_str = url[start_loc:end_loc]
        try:
            survey_id = int(survey_id_str)
            print(f"[OK] Got surveyId: {survey_id}")
            return survey_id
        except ValueError as e:
            print(f"[X] Convert to int failed: {e}")
    else:
        print("[X] No surveyId= in URL")

    return None

def test_api(context, survey_id):
    """测试API调用"""
    print("\n=== Test 3: API Call ===")

    cookie_str = get_cookies(context)
    print(f"Cookie length: {len(cookie_str)}")

    # 测试不同page_size
    for page_size in [10, 20, 50, 200]:
        print(f"\n--- Testing page_size={page_size} ---")
        df, total = get_page_df(cookie_str, survey_id, page_size, 1)

        if total > 0:
            print(f"[OK] Got {len(df)} records from API, total={total}")
        else:
            print(f"[X] Failed to get data")

    return True

def test_download_all(context, survey_id):
    """测试完整下载"""
    print("\n=== Test 4: Download All ===")

    cookie_str = get_cookies(context)

    print("Starting download...")

    # 先获取原始数据检查
    from api import get_page_df
    df_raw, total, _, _ = get_page_df(cookie_str, survey_id, 200, 1, download=True)
    print(f"Raw data: {len(df_raw)} rows")

    # 检查哪些列有*号
    for col in df_raw.columns:
        star_count = (df_raw[col] == "*").sum()
        if star_count > 0:
            print(f"  Column '{col[:30]}...' has {star_count} '*' values")

    try:
        df = download_all_data(cookie_str, survey_id, page_size=10)
        print(f"[OK] Downloaded {len(df)} records")
        print(f"  Column count: {len(df.columns)}")

        # 检查status列
        if 'status' in df.columns:
            print(f"  Status values: {df['status'].unique()}")

        # 保存测试 - 用csv避免编码问题
        test_file = "debug_test_output.csv"
        save_to_file(df, test_file)
        print(f"[OK] Saved to {test_file}")
        return True
    except Exception as e:
        print(f"[X] Download failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_pagination(page):
    """测试分页信息"""
    print("\n=== Test 5: Pagination ===")

    try:
        # 获取分页信息
        total_elem = page.locator('.el-pagination__total').first
        if total_elem.count() > 0:
            total_text = total_elem.inner_text()
            print(f"Total element: {total_text}")

        # 获取当前页码
        current_page = page.locator('.el-pagination .is-active').first
        if current_page.count() > 0:
            page_text = current_page.inner_text()
            print(f"Current page: {page_text}")

        # 获取表格行数
        rows = page.locator('table tbody tr').all()
        print(f"Table rows: {len(rows)}")

        # 获取表格数据 - userId
        for i, row in enumerate(rows[:5]):
            cells = row.locator('td').all()
            if cells:
                first_cell = cells[0].inner_text()
                print(f"Row {i+1} first cell: {first_cell[:30]}")

    except Exception as e:
        print(f"[X] Pagination test failed: {e}")
        import traceback
        traceback.print_exc()

def main():
    print("=" * 50)
    print("Credamo Debug Tool")
    print("=" * 50)

    try:
        # Test 1: 连接浏览器
        p, browser, context, page = test_browser()

        # Test 2: 获取surveyId
        survey_id = test_survey_id(page)
        if not survey_id:
            print("\nPlease open a project in browser first!")
            print("After opening, press Enter to continue...")
            input()
            survey_id = test_survey_id(page)

        if survey_id:
            # Test 3: API调用
            test_api(context, survey_id)

            # Test 4: 完整下载
            test_download_all(context, survey_id)

            # Test 5: 分页信息
            test_pagination(page)

        print("\n=== Debug Complete ===")
        print("Browser stays open, you can continue manual operation")
        print("Press Enter to exit...")
        input()

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

    finally:
        try:
            browser.close()
            p.stop()
        except:
            pass

if __name__ == "__main__":
    main()
