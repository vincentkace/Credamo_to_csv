from playwright.sync_api import sync_playwright
import os

USER_DATA_DIR = os.path.join(os.path.dirname(__file__), "browser_data")

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

def launch_browser(connect_existing=False):
    """启动带反爬措施的浏览器

    Args:
        connect_existing: True=连接已有Chrome, False=启动新Chrome
    """
    p = sync_playwright().start()

    if connect_existing:
        # 连接已启动的Chrome（开发者模式）
        browser = p.chromium.connect_over_cdp("http://localhost:9222")

        # CDP连接需要通过context来获取页面
        # 获取第一个context（通常CDP连接只有一个context）
        if browser.contexts:
            context = browser.contexts[0]
            all_pages = context.pages
        else:
            context = browser.new_context()
            all_pages = []

        credamo_pages = []
        focused_page = None

        # 遍历所有页面找Credamo
        for page in all_pages:
            if "credamo.com" in page.url:
                try:
                    is_visible = page.evaluate("() => document.visibilityState === 'visible'")
                    if is_visible:
                        focused_page = page
                        break
                except:
                    pass
                credamo_pages.append(page)

        if not focused_page:
            if credamo_pages:
                focused_page = credamo_pages[0]
            elif all_pages:
                # 没有Credamo页面，使用第一个页面
                focused_page = all_pages[0]
            else:
                # 没有页面，创建新的
                focused_page = context.new_page()

        page = focused_page
    else:
        # 启动新的Chrome
        context = p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=False,
            channel="chrome",
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-default-browser-check",
                "--disable-dev-shm-usage",
            ]
        )
        page = context.new_page()
        browser = page.context.browser

    page.add_init_script(ANTI_DEBUG_SCRIPT)
    context = page.context
    return p, browser, context, page

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
