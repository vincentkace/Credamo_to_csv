# 文件名：credamo_bypass.py
# 运行前安装：
# pip install playwright
# python -m playwright install chromium

from playwright.sync_api import sync_playwright
import os

USER_DATA_DIR = os.path.join(os.path.dirname(__file__), "browser_data")

URL = "https://www.credamo.com/survey.html?surveyId=31273164362#/dataClean"

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        channel="chrome",
        user_data_dir=USER_DATA_DIR,
        args=[
            "--start-maximized",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--no-default-browser-check",
            "--disable-dev-shm-usage",
        ]
    )

    context = browser.new_context(
        viewport=None
    )

    page = context.new_page()

    # ===== 页面执行前注入（核心）=====
    page.add_init_script("""
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
    """)

    # 打开页面
    page.goto(URL, wait_until="domcontentloaded")

    print("已打开页面")
    print("你现在可以手动操作，或打开 DevTools / MCP")

    input("按回车退出...")
    browser.close()