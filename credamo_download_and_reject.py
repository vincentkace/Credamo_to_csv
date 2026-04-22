# conda create -n py36 python=3.6 openpyxl pandas selenium requests pyinstaller
# pyinstaller -F credamo_download_and_reject.py --hidden-import "openpyxl.cell._writer"

import time
import openpyxl
import pandas as pd
import tkinter as tk
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import requests
import json

def open_credamo(browser):
    browser.get("https://www.credamo.com")
    # 检测登录
    login = False
    for i in range(5):
        try:
            show_execute_info("请登录Credamo账号。")
            browser.find_element_by_class_name("login").click()
            time.sleep(1)
            for cookie in browser.get_cookies():
                if cookie['name']=='credamo-dms-auth':
                    login=True
                    break
            # print("未检测到登录，请登录Credamo账号。")
        except:
            time.sleep(1)
            pass
            # print("已登陆。")
    if login==True:
        show_execute_info("已登陆，请在浏览器中手动打开您需要拒绝被试的项目。")
        print("已登陆，请在浏览器中手动打开您需要拒绝被试的项目。")
    else:
        show_execute_info("请登录账号，然后打开一个项目。")
        print("已登陆，请在浏览器中手动打开您需要拒绝被试的项目。")
    show_execute_info("准备好excel后点击自动拒绝被试")
    print("已登陆，请在浏览器中手动打开您需要拒绝被试的项目。")
    
def get_surveyId(browser):
    url = browser.current_url
    try:
        # 获得surveyId
        startloc = url.index("surveyId")+len("surveyId=")
        endloc = url.index("#")
        surveyId = url[url.index("surveyId")+len("surveyId="):url.index("#")]
    except:
        print("还没有打开项目,读取不到surveyId,请打开一个项目")
        show_execute_info("还没有打开项目,读取不到surveyId,请打开一个项目")
        return 0
    
    #检测是否打开数据清理页面，如果没有则自动点击清理
    try:
        browser.find_element_by_class_name("iconfont icon-shaixuan")
        # 如果找到，表明已经打开数据清理页面
        print("已打开数据清理页面")
        show_execute_info("已打开数据清理页面")
    except:    
    # 如果报错，没有打开数据清理页面，自动点击“数据清理”
        try:
            browser.find_element_by_class_name("iconfont icon-shaixuan")
        except:
            browser.find_element_by_link_text("数据").click()
            time.sleep(3)
    
    return int(surveyId)

def set_page_size(browser,page_size):
    page_sizes = [5,10,30,50,100]
    try:
        size_choise = page_sizes.index(page_size)
    except:
        print("没有该条数/页的选项，请检查")
        show_execute_info("没有该条数/页的选项，请检查")
        return -2
    # 设置100页
    set_size = False
    retry_time = 0
    while (not set_size) and retry_time <= 5:
        try:
            browser.find_element_by_class_name('el-input__inner').click()
            time.sleep(1)
            pageSizes = browser.find_elements_by_class_name('el-select-dropdown__item')
            pageSizes[size_choise].click()
            page_size = page_sizes[size_choise]
            set_size = True
            return page_size
        except:
            print("设置条数/页失败，正在重试")
            show_execute_info("设置条数/页失败，正在重试")
            retry_time += 1
    print("设置页码失败，请检查网页。")
    show_execute_info("设置页码失败，请检查网页。")

def go_to_page(browser,page):
    loc = WebDriverWait(browser.find_element_by_class_name('el-pagination__jump'), 10).until(
        EC.element_to_be_clickable((By.CLASS_NAME, 'el-input__inner'))
    )
    loc.send_keys(Keys.CONTROL+'a')     #全选
    loc.send_keys(Keys.DELETE)		# 删除，清空
    loc.send_keys(page)	# 写入新的值
    loc.send_keys(Keys.ENTER)
    return page

def set_encoding(browser):
    time.sleep(1)
    browser.find_element_by_link_text("数据").click()
    time.sleep(2)
    # delete some click that cause bugs 20231210
    # browser.find_element_by_xpath("/html/body/div[@id='survey_bg']/div[4]/div[1]/div[@class='route']/div[@class='button2']").click()
    # time.sleep(1)
    # browser.find_element_by_xpath("/html/body/div[@id='survey_bg']/div[4]/div[@class='resultView']/div[@class='search-box']/div[@class='popover'][4]").click()
    # time.sleep(1)
    # browser.find_element_by_xpath("/html/body/div[@id='survey_bg']/div[4]/div[1]/div[@class='route']/div[@class='button1']").click()
    # time.sleep(1)

def get_page_df(browser,surveyId,page_size,page_num,download=False):
    try:
        time.sleep(1)
        cookies = browser.get_cookies()
        cookie_str = ""
        for cookie in cookies:
            cookie_str = "{}={}; ".format(cookie['name'],cookie['value']) + cookie_str
        cookie_str = cookie_str[:-2]
        
        headers = {"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
                    "referer": "https://www.credamo.com/survey.html?surveyId=%d}" % surveyId,
                    "cookie":cookie_str}
        url = "https://www.credamo.com/v1/cleanVar/qstOverviewBySurId/%d?currPageSize=%d&currPageIndex=%d"  % (surveyId,page_size,page_num)
    except:
        print("获取cookie失败，请重试。")
        show_execute_info("获取cookie失败，请重试。")
        return []
    try:
        resp = requests.get(url=url,headers=headers)
        if resp.status_code == 200:
            output = json.loads(resp.content.decode('utf8'))
            data = output['data']
            ques_headers = data['header']
            total_cnt = output['total']
            ques_headers_kv = {}
            for header in ques_headers:
                ques_headers_kv[header["id"]] = header['qNum']+" "+header['questionName']
            df = pd.DataFrame(output['data']['rowList'])
            #如果下载，则不替换列名称，最后再替换
            if not download:
                df.columns = [ques_headers_kv[id] if id not in ['status', 'answerId', 'userId'] else id for id in df.columns]
                return df,total_cnt
            else:
                return df,total_cnt,ques_headers_kv,ques_headers
        else:
            print("无法登录到问卷页面")
            show_execute_info("无法登录到问卷页面")
            return pd.DataFrame([]),0
    except:
        print("无法get问卷页面")
        show_execute_info("无法get问卷页面")
        return pd.DataFrame([]),0

def download_data(browser,download_name):
    surveyId = get_surveyId(browser)
    set_encoding(browser)
    page_size = set_page_size(browser,page_size=10)
    page_num = 1
    page_num = go_to_page(browser,page_num)
    page_df,total_cnt,ques_headers_kv,ques_headers = get_page_df(browser,surveyId,page_size,page_num,download=True)
    total_page_num = total_cnt//page_size+1
    page_dfs = pd.DataFrame([])
    for page_num in range(total_page_num):
        page_num += 1
        print(page_num)
        # go_to_page(browser,page_num)
        # time.sleep(5)
        page_df,total_cnt,ques_headers_kv,_ = get_page_df(browser,surveyId,page_size,page_num,download=True)
        if 'userId' in page_df.columns:
            page_df.set_index('userId')
            if str(page_dfs.shape)=="(0, 0)":
                page_dfs = page_df
            else:
                page_dfs = pd.concat([page_dfs,page_df],ignore_index=True)
    page_dfs.columns = [
        ques_headers_kv[id] 
        if id not in ['status', 'answerId', 'userId'] 
        else id 
        for id in page_dfs.columns
    ]
    page_dfs = page_dfs[['status', 'answerId', 'userId'] + [ques_headers_kv[ques_header['id']] for ques_header in ques_headers]]
    page_dfs = page_dfs[(page_dfs=="*").sum(axis=1)==0] #剔除拒绝的
    download_name_str = download_name.get('0.0','end').strip()+"_"+time.strftime('%Y%m%d_%H%M')+".xlsx"
    page_dfs.to_excel(download_name_str)
    show_execute_info("{}下载完成".format(download_name_str))

def get_userId_loc(excel_name,page_df,page_num,autobatchReject):
    chosen_ids = excel_name.get("1.0","end").strip().split('\n')
    if 'userId' in page_df.columns:
        page_userIds = page_df['userId'].tolist()
    else:
        show_execute_info("第%d页无被试" % page_num)
        return []
    page_chosen_ids = list(set(chosen_ids) & set(page_userIds))
    chosen_rows = []
    for chosen_id in page_chosen_ids:
        chosen_row = page_userIds.index(chosen_id)+1
        chosen_rows.append(chosen_row)
        xpath_expression = f"//table[@style='margin-top: 0px; width: 415px;']/tbody/tr[{chosen_row}]/td[1]/div/span"
        browser.find_element_by_xpath(xpath_expression).click()
        # 批量拒绝
    browser.find_element_by_class_name("el-dropdown").click()
    time.sleep(1)
    if autobatchReject == True:
            browser.find_elements_by_class_name("el-dropdown-menu__item")[1].click() # 点击拒绝选中数据
            time.sleep(3)
            try:
                WebDriverWait(browser, 10).until(EC.element_to_be_clickable((By.XPATH, "//div[@class='el-select' and @style='width: 380px;']"))).click()  # 点击请选择
            except TimeoutException:
                ok_button_locator = (By.XPATH, "//button[@class='el-button el-button--default el-button--small el-button--primary ']/span[contains(text(), '确定')]")
                WebDriverWait(browser, 10).until(EC.element_to_be_clickable(ok_button_locator)).click()
                show_execute_info("第%d页无拒绝被试" % page_num)
                print("第%d页无拒绝被试" % page_num)
                time.sleep(3)
                return []
            reject_reason_li_locator = (By.XPATH, "//li[contains(@class, 'el-select-dropdown__item') and span[text()='填写内容不符合要求，请认真阅读并仔细填答']]")
            WebDriverWait(browser, 10).until(EC.element_to_be_clickable(reject_reason_li_locator)).click()
            # 等待第一个按钮的操作完成，例如等待下拉框消失
            # WebDriverWait(browser, 10).until_not(EC.presence_of_element_located((By.XPATH, reject_reason_li_locator)))
            reject_button_locator = (By.XPATH, "//div[@class='el-dialog__footer']//button[@class='el-button el-button--primary' and span[text()='批量拒绝']]")
            WebDriverWait(browser, 10).until(EC.element_to_be_clickable(reject_button_locator)).click()
            print("第%d页已拒绝%d个被试" % (page_num,len(chosen_rows)))
            time.sleep(3)
    return chosen_rows 

def batchReject(browser,excel_name,page_num_assign_text,autoReject=True):
    surveyId = get_surveyId(browser)
    page_size = set_page_size(browser,page_size=10)
    page_num = 1
    page_num = go_to_page(browser,page_num)
    page_df,total_cnt = get_page_df(browser,surveyId,page_size,page_num)
    total_page_num = total_cnt//page_size+1
    if autoReject:
        for page_num in range(total_page_num):
            page_num += 1
            # print(page_num)
            go_to_page(browser,page_num)
            time.sleep(5)
            page_df,total_cnt = get_page_df(browser,surveyId,page_size,page_num)
            # print(total_cnt)
            userId_loc = get_userId_loc(excel_name,page_df,page_num,autoReject)
            # print(userId_loc)
        show_execute_info('所有页面已拒绝。\n你可以打开另一个项目，清空原用户ID后粘贴新项目待拒绝用户ID，重新点击拒绝被试。\n或者关闭浏览器，关闭本程序')
        # batchAccept(browser,excel_name,page_num_assign_text,autoReject=True)
    else:
        #手动拒绝
        try:
            page_num_assign = int(page_num_assign_text.get('0.0','end').strip())
        except:
            print("无法读取页面数，请在上方小方框中输入正确的页面数字")
            show_execute_info("无法读取页面数，请在上方小方框中输入正确的页面数字")
            return 0
        if page_num_assign <= 0 or page_num_assign > total_cnt//page_size+1:
            print("输入的页面数字超过答卷范围，请检查页面数")
            show_execute_info("输入的页面数字超过答卷范围，请检查页面数")
        go_to_page(browser,page_num_assign)
        time.sleep(5)
        page_df,total_cnt = get_page_df(browser,surveyId,page_size,page_num_assign)
        # print(total_cnt)
        userId_loc = get_userId_loc(excel_name,page_df,page_num_assign,autoReject)
        # print(userId_loc)
        print('页面%d已选中待拒绝被试，可以手动在浏览器中点击拒绝。\n' % page_num_assign)
        show_execute_info('页面%d已选中待拒绝被试，可以手动在浏览器中点击拒绝。\n'%page_num_assign)

def get_accept_userId_loc(excel_name,page_df,page_num,autobatchReject):
    page_userIds = page_df['userId'].tolist()
    reject_ids = excel_name.get("1.0","end").strip().split('\n')
    page_unselected_ids = page_df[page_df['status']==1]['userId'].tolist() # list(set(chosen_ids) & set(page_userIds))
    page_chosen_ids = list(set(page_unselected_ids) - set(reject_ids))
    chosen_rows = []
    for chosen_id in page_chosen_ids:
        chosen_row = page_userIds.index(chosen_id)+1
        chosen_rows.append(chosen_row)
        xpath_expression = f"//table[@style='margin-top: 0px; width: 415px;']/tbody/tr[{chosen_row}]/td[1]/div/span"
        browser.find_element_by_xpath(xpath_expression).click()

    browser.find_element_by_class_name("el-dropdown").click()
    time.sleep(1)
    if autobatchReject == True:
        browser.find_elements_by_class_name("el-dropdown-menu__item")[0].click() # 点击采纳选中数据
        time.sleep(1)
        confirm_result_button_xpath = f"//span[contains(text(), '确定')]"#
        confirm_result_buttons = browser.find_elements_by_xpath(confirm_result_button_xpath)
        # 遍历所有匹配的元素
        for button in confirm_result_buttons:
            # 判断元素是否可点击
            if button.is_enabled() and button.is_displayed():
                # 执行点击操作
                button.click()
                # 只点击第一个可点击的元素，如果需要点击所有可点击的元素，可以去掉break语句
                # print("第%d页已接受%d个被试" % (page_num,len(chosen_rows)))
                show_execute_info("第%d页已接受%d个被试" % (page_num,len(chosen_rows)))
                break
    else:
        # show_execute_info('页面%d已选中待接受被试，可以手动在浏览器中点击接受。\n'%page_num)
        show_execute_info("页面%d已选中%d个待接受被试，可以手动在浏览器中点击接受。\n" % (page_num,len(chosen_rows)))
    return 

def batchAccept(browser,excel_name,page_num_assign_text,autoReject=True):
    surveyId = get_surveyId(browser)
    page_size = set_page_size(browser,page_size=10)
    page_num = 1
    page_num = go_to_page(browser,page_num)
    page_df,total_cnt = get_page_df(browser,surveyId,page_size,page_num)
    total_page_num = total_cnt//page_size+1
    if autoReject:
        for page_num in range(total_page_num):
            page_num += 1
            # print(page_num)
            go_to_page(browser,page_num)
            time.sleep(5)
            page_df,total_cnt = get_page_df(browser,surveyId,page_size,page_num)
            # print(total_cnt)
            get_accept_userId_loc(excel_name,page_df,page_num,autoReject)
            # print(userId_loc)
        show_execute_info('所有页面已接受。\n你可以打开另一个项目，清空原用户ID后粘贴新项目待拒绝用户ID，重新点击拒绝被试。\n或者关闭浏览器，关闭本程序')
        # show_execute_info('所有页面已拒绝。\n你可以打开另一个项目，清空原用户ID后粘贴新项目待拒绝用户ID，重新点击拒绝被试。\n或者关闭浏览器，关闭本程序')
    else:
        #手动拒绝
        try:
            page_num_assign = int(page_num_assign_text.get('0.0','end').strip())
        except:
            show_execute_info("无法读取页面数，请在上方小方框中输入正确的页面数字")
            # show_execute_info("无法读取页面数，请在上方小方框中输入正确的页面数字")
            return 0
        if page_num_assign <= 0 or page_num_assign > total_cnt//page_size+1:
            show_execute_info("输入的页面数字超过答卷范围，请检查页面数")
            # show_execute_info("输入的页面数字超过答卷范围，请检查页面数")
        go_to_page(browser,page_num_assign)
        time.sleep(5)
        page_df,total_cnt = get_page_df(browser,surveyId,page_size,page_num_assign)
        # print(total_cnt)
        get_accept_userId_loc(excel_name,page_df,page_num_assign,autoReject)
        # print(userId_loc)
        show_execute_info('页面%d已选中待接受被试，可以手动在浏览器中点击接受。\n' % page_num_assign)
        # show_execute_info('页面%d已选中待拒绝被试，可以手动在浏览器中点击拒绝。\n'%page_num_assign)

def show_execute_info(var,cmd=False):
    if cmd:
        print(var)
    else:
        execute_info.insert("0.0", '\n' + time.strftime('%Y-%m-%d %H:%M:%S ') + var + '\n')


window = tk.Tk()
window.title("批量拒绝被试")
window.geometry("600x450")

login_Frame = tk.Frame(window)
login_Frame.pack()

open_button = tk.Button(login_Frame, text='打开Credamo网站', width=15, height=1,
                        command=lambda:open_credamo(browser))
open_button.pack(side="left")

blank1 = tk.Label(login_Frame, text="  ",
                                  width=3)
blank1.pack(side="left")

download_button = tk.Button(login_Frame, text='下载数据', width=15, height=1,
                        command=lambda:download_data(browser,download_name))
download_button.pack(side="left")

download_name = tk.Text(login_Frame, height=1, width=20)
download_name.insert("0.0", 'credamo_data')
download_name.pack(side="left")

download_format = tk.Label(login_Frame, text="_YYYYmmdd_HHMMSS.xlsx",
                                  width=23)
download_format.pack(side="left")

#拒绝被试list
excel_instruc = tk.Label(window, text="请在下面粘贴待拒绝被试的用户ID",
                                width=30, height=2)
excel_instruc.pack()

excel_name = tk.Text(window, height=10)
excel_name.pack()

reject_Frame = tk.Frame(window)
reject_Frame.pack()

reject_button = tk.Button(reject_Frame, text='自动拒绝被试', width=10, height=1,
                        command=lambda:batchReject(browser,excel_name,page_num_assign_text,True))
reject_button.pack(side="left")

blank1 = tk.Label(reject_Frame, text="  ",
                                  width=3)
blank1.pack(side="left")

reject_button = tk.Button(reject_Frame, text='自动接受剩下的被试', width=15, height=1,
                        command=lambda:batchAccept(browser,excel_name,page_num_assign_text,True))
reject_button.pack(side="left")

blank1 = tk.Label(reject_Frame, text="  ",
                                  width=3)
blank1.pack(side="left")

choose_button = tk.Button(reject_Frame, text='手动拒绝被试', width=10, height=1,
                            command=lambda:batchReject(browser,excel_name,page_num_assign_text,False))
choose_button.pack(side="left")

page_instruc1 = tk.Label(reject_Frame, text="第",
                                width=2)
page_instruc1.pack(side="left")

page_num_assign_text = tk.Text(reject_Frame, height=1, width=4)
page_num_assign_text.insert("0.0", '1')
page_num_assign_text.pack(side="left")

page_instruc2 = tk.Label(reject_Frame, text="页",
                                width=2)
page_instruc2.pack(side="left")


blank_instruc = tk.Label(window, text="----下面是提示----",
                                # bg="green", font=('Arial',12),
                                width=30, height=2)
blank_instruc.pack()

execute_info = tk.Text(window, height=10)
first_info = '一共三个步骤，登录Credamo后打开一个项目，粘贴待拒绝用户ID，最后拒绝被试。\n请在点击第一个按钮登录Credamo，打开您的项目'
show_execute_info(first_info)
execute_info.pack()

# Specify the path to chromedriver executable
# chrome_path = r'C:\Program Files\Google\Chrome\Application\chromedriver.exe'
# browser = webdriver.Chrome(executable_path=chrome_path)
browser = webdriver.Chrome()

window.mainloop()
