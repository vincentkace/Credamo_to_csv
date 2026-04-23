from playwright.sync_api import sync_playwright
import os
import time
import sys
import json
import urllib.request
from config import load_config, get_browser_executable, start_browser_with_cdp

ANTI_DEBUG_SCRIPT = """
(() => {
    // ========= 1. 干掉 debugger =========
    const rawFunction = Function.prototype.constructor;

    Function.prototype.constructor = function(code){
        try{
            if(typeof code === 'string' && code.includes('debugger')){
                code = code.replace(/debugger/g,'');
            }
        }catch(e){}
        return rawFunction.call(this, code);
    };

    const rawEval = window.eval;
    window.eval = function(code){
        try{
            if(typeof code === 'string' && code.includes('debugger')){
                code = code.replace(/debugger/g,'');
            }
        }catch(e){}
        return rawEval(code);
    };

    // ========= 2. 拦截可疑定时器 =========
    const rawSetInterval = window.setInterval;
    window.setInterval = function(fn, t){
        try{
            const s = fn && fn.toString ? fn.toString() : '';
            if(
                s.includes('debugger') ||
                s.includes('about:blank') ||
                s.includes('performance.now')
            ){
                console.log('Blocked interval');
                return 0;
            }
        }catch(e){}
        return rawSetInterval(fn, t);
    };

    const rawSetTimeout = window.setTimeout;
    window.setTimeout = function(fn, t){
        try{
            const s = fn && fn.toString ? fn.toString() : '';
            if(s.includes('debugger')){
                return 0;
            }
        }catch(e){}
        return rawSetTimeout(fn, t);
    };

    // ========= 3. 阻止跳转 about:blank =========
    const rawAssign = window.location.assign.bind(window.location);
    const rawReplace = window.location.replace.bind(window.location);

    window.location.assign = function(url){
        if(String(url).includes('about:blank')) return;
        rawAssign(url);
    };

    window.location.replace = function(url){
        if(String(url).includes('about:blank')) return;
        rawReplace(url);
    };

    // ========= 4. webdriver隐藏 =========
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined
    });

    // ========= 5. DevTools尺寸检测绕过 =========
    Object.defineProperty(window, 'outerWidth', {
        get(){ return window.innerWidth; }
    });

    Object.defineProperty(window, 'outerHeight', {
        get(){ return window.innerHeight; }
    });

    // ========= 6. console.clear 禁止 =========
    console.clear = function(){};

    // ========= 7. performance.now稳定 =========
    const rawNow = performance.now.bind(performance);
    performance.now = function(){
        return rawNow();
    };
})();
"""

def extract_survey_id(url):
    """从URL中提取surveyId"""
    if not url:
        return None
    try:
        if "surveyId=" in url:
            start_loc = url.index("surveyId=") + len("surveyId=")
            end_chars = ['#', '?', '&']
            end_loc = len(url)
            for char in end_chars:
                pos = url.find(char, start_loc)
                if pos != -1 and pos < end_loc:
                    end_loc = pos
            return int(url[start_loc:end_loc])
    except:
        pass
    return None

def get_cdp_pages(cdp_port):
    """通过CDP HTTP接口获取所有页面的实时信息"""
    try:
        req = urllib.request.urlopen(f"http://localhost:{cdp_port}/json", timeout=3)
        data = json.loads(req.read().decode("utf-8"))
        return data
    except:
        return []

def find_survey_id_via_cdp(cdp_port):
    """通过CDP接口查找surveyId，返回(survey_id, target_id)"""
    pages = get_cdp_pages(cdp_port)
    for pg in pages:
        url = pg.get("url", "")
        sid = extract_survey_id(url)
        if sid:
            return sid, pg.get("id"), url
    return None, None, None

def get_page_by_target(browser, target_id):
    """通过target_id找到playwright的page对象"""
    for ctx in browser.contexts:
        for pg in ctx.pages:
            try:
                if hasattr(pg, 'target') and callable(getattr(pg, 'target')):
                    continue
                cdp_session = ctx.new_cdp_session(pg)
                target_info = cdp_session.send("Target.getTargetInfo", {})
                cdp_session.detach()
                if target_info.get("targetInfo", {}).get("targetId") == target_id:
                    return pg
            except:
                pass
    return None

def get_all_page_urls(browser, cdp_port):
    """获取所有页面URL（优先CDP实时接口）"""
    cdp_pages = get_cdp_pages(cdp_port)
    if cdp_pages:
        return [pg.get("url", "") for pg in cdp_pages]
    urls = []
    for ctx in browser.contexts:
        for pg in ctx.pages:
            try:
                urls.append(pg.url)
            except:
                pass
    return urls

def connect_browser(config):
    """连接已启动的浏览器（通过CDP）"""
    p = sync_playwright().start()
    browser_type = config.get("browser_type", "chrome")
    cdp_port = config.get("cdp_port", 9222)

    try:
        if browser_type == "firefox":
            browser = p.firefox.connect_over_cdp(f"http://localhost:{cdp_port}")
        elif browser_type == "msedge":
            browser = p.msedge.connect_over_cdp(f"http://localhost:{cdp_port}")
        else:
            browser = p.chromium.connect_over_cdp(f"http://localhost:{cdp_port}")
    except Exception as e:
        print(f"连接浏览器失败: {e}")
        print(f"请确保Chrome已启动并开启了CDP端口 {cdp_port}")
        print(f"启动命令: chrome --remote-debugging-port={cdp_port}")
        raise

    page = None
    survey_id = None

    cdp_pages = get_cdp_pages(cdp_port)
    print(f"浏览器连接成功，CDP发现 {len(cdp_pages)} 个页面")

    for pg_info in cdp_pages:
        url = pg_info.get("url", "")
        sid = extract_survey_id(url)
        if sid:
            survey_id = sid
            print(f"  找到问卷ID: {sid} (URL: {url})")
            break

    if browser.contexts and browser.contexts[0].pages:
        page = browser.contexts[0].pages[0]
    else:
        ctx = browser.new_context()
        page = ctx.new_page()

    page.add_init_script(ANTI_DEBUG_SCRIPT)
    context = page.context
    return p, browser, context, page, survey_id

def launch_browser():
    """启动带反爬措施的浏览器（自动启动浏览器）"""
    config = load_config()
    browser_type = config.get("browser_type", "chrome")
    cdp_port = config.get("cdp_port", 9222)
    user_data_dir = config.get("user_data_dir", "")
    executable_path = get_browser_executable(browser_type, config.get("browser_path", ""))

    if not executable_path:
        print(f"错误: 未找到 {browser_type} 浏览器，请检查配置或手动指定路径")
        sys.exit(1)

    os.makedirs(user_data_dir, exist_ok=True)

    from config import is_cdp_running
    if is_cdp_running(cdp_port):
        print(f"CDP端口 {cdp_port} 已有浏览器连接，直接连接...")
    else:
        print(f"正在启动 {browser_type} 浏览器...")
        start_browser_with_cdp(browser_type, executable_path, cdp_port, user_data_dir)
        time.sleep(2)

    return connect_browser(config)

def get_cookies(context):
    """获取浏览器cookie字符串"""
    cookies = context.cookies()
    cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
    return cookie_str

def is_logged_in(context):
    """检查是否已登录Credamo"""
    cookies = context.cookies()
    for cookie in cookies:
        if cookie['name'] == 'credamo-dms-auth':
            return True
    return False
