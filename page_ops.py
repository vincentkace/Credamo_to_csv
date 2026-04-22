import time

PAGE_SIZES = [5, 10, 30, 50, 100]

def get_survey_id(page):
    """从当前URL获取surveyId（从URL中提取）"""
    url = page.url
    try:
        # 新URL格式: https://www.credamo.com/survey.html?surveyId=xxx#/dataClean
        if "surveyId=" in url:
            start_loc = url.index("surveyId=") + len("surveyId=")
            # 找到#或?或字符串结尾
            end_chars = ['#', '?', '&']
            end_loc = len(url)
            for char in end_chars:
                pos = url.find(char, start_loc)
                if pos != -1 and pos < end_loc:
                    end_loc = pos
            survey_id = url[start_loc:end_loc]
            return int(survey_id)
    except Exception as e:
        print(f"获取surveyId失败: {e}")
    return None


def is_data_clean_page(page):
    """检查是否在数据清理页面"""
    try:
        # 查找筛选图标（数据清理页面的标志）
        page.locator(".iconfont.icon-shaixuan").wait_for(timeout=3000)
        return True
    except:
        return False


def go_to_data_clean_page(page):
    """如果没有在数据清理页面，点击进入"""
    # 先检查是否已经在数据清理页面
    if is_data_clean_page(page):
        print("已在数据清理页面")
        return

    try:
        page.locator("text=数据清理").click()
        time.sleep(2)
    except Exception as e:
        print(f"进入数据清理页面失败: {e}")


def set_page_size(page, page_size):
    """设置每页显示条数"""
    if page_size not in PAGE_SIZES:
        print(f"不支持的页面大小: {page_size}")
        return False

    size_choice = PAGE_SIZES.index(page_size)
    retry_time = 0

    while retry_time <= 5:
        try:
            # 点击每页显示条数的下拉框
            page.locator('.el-input__inner').first.click()
            time.sleep(1)

            # 选择对应的选项
            page.locator(f'.el-select-dropdown__item >> nth={size_choice}').click()
            time.sleep(1)
            return True
        except Exception as e:
            print(f"设置页面大小失败，重试中... ({retry_time + 1}/5)")
            retry_time += 1

    print("设置页面大小失败")
    return False


def go_to_page(page, page_num):
    """跳转到指定页码"""
    try:
        # 找到分页输入框
        pagination_input = page.locator('.el-pagination__jump .el-input__inner')
        pagination_input.fill(str(page_num))
        pagination_input.press('Enter')
        time.sleep(1)
        return page_num
    except Exception as e:
        print(f"跳页失败: {e}")
        return None


def select_user(page, row_num):
    """勾选指定行的用户"""
    try:
        # 表格中的checkbox，row_num从1开始
        checkbox = page.locator(f'table tbody tr:nth-child({row_num}) td:first-child span').first
        checkbox.click()
        return True
    except Exception as e:
        print(f"勾选用户失败: {e}")
        return False


def open_dropdown_menu(page):
    """打开批量操作下拉菜单"""
    try:
        page.locator('.el-dropdown').click()
        time.sleep(1)
        return True
    except Exception as e:
        print(f"打开下拉菜单失败: {e}")
        return False


def batch_reject(page, auto=True):
    """批量拒绝被试

    Args:
        page: Playwright page对象
        auto: True自动拒绝，False只是选中待拒绝用户
    """
    try:
        # 打开下拉菜单
        open_dropdown_menu(page)

        # 点击拒绝选项（通常是第二个）
        page.locator('.el-dropdown-menu__item').nth(1).click()
        time.sleep(2)

        if auto:
            try:
                # 点击选择框
                page.locator('.el-select').first.click()
                time.sleep(1)

                # 选择拒绝原因
                page.locator('.el-select-dropdown__item:has-text("填写内容不符合要求")').click()
                time.sleep(1)

                # 点击确定按钮
                page.locator('button:has-text("批量拒绝")').click()
                time.sleep(3)
                return True
            except Exception as e:
                # 可能没有需要拒绝的用户
                print(f"批量拒绝完成或无需拒绝: {e}")
                try:
                    page.locator('button:has-text("确定")').click()
                except:
                    pass
                return False
        return True
    except Exception as e:
        print(f"批量拒绝失败: {e}")
        return False


def batch_accept(page, auto=True):
    """批量接受被试

    Args:
        page: Playwright page对象
        auto: True自动接受，False只是选中待接受用户
    """
    try:
        # 打开下拉菜单
        open_dropdown_menu(page)

        # 点击接受选项（通常是第一个）
        page.locator('.el-dropdown-menu__item').nth(0).click()
        time.sleep(2)

        if auto:
            try:
                # 点击确定按钮
                page.locator('button:has-text("确定")').first.click()
                time.sleep(2)
                return True
            except Exception as e:
                print(f"批量接受完成: {e}")
                return False
        return True
    except Exception as e:
        print(f"批量接受失败: {e}")
        return False


def get_current_page_users(page):
    """获取当前页面的用户列表"""
    try:
        # 获取表格中所有userId
        rows = page.locator('table tbody tr').all()
        user_ids = []
        for row in rows:
            # 需要从行数据中提取userId
            # 这里需要根据实际DOM结构调整
            pass
        return user_ids
    except Exception as e:
        print(f"获取用户列表失败: {e}")
        return []
