import os
import json
import subprocess
import time
import urllib.request

_CREDAMO_DIR = os.path.dirname(__file__)

CONFIG_FILE = os.path.join(_CREDAMO_DIR, "config.json")

PROJECT_ROOT = os.path.dirname(_CREDAMO_DIR)

DEFAULT_CONFIG = {
    "browser_type": "chrome",
    "browser_path": "",
    "cdp_port": 9222,
    "user_data_dir": os.path.join(PROJECT_ROOT, "browser_data"),
    "headless": False
}

BROWSER_PATHS = {
    "chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ],
    "msedge": [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ],
    "firefox": [
        r"C:\Program Files\Mozilla Firefox\firefox.exe",
        r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
    ]
}

def load_config():
    """加载配置文件"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                merged = DEFAULT_CONFIG.copy()
                merged.update(saved)
                if "user_data_dir" not in saved:
                    merged["user_data_dir"] = DEFAULT_CONFIG["user_data_dir"]
                return merged
        except:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(config):
    """保存配置文件"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def find_browser_path(browser_type):
    """自动查找浏览器路径"""
    for path in BROWSER_PATHS.get(browser_type, []):
        if os.path.exists(path):
            return path
    return ""

def get_browser_executable(browser_type, custom_path):
    """获取浏览器可执行文件路径"""
    if custom_path and os.path.exists(custom_path):
        return custom_path
    return find_browser_path(browser_type)

def is_cdp_running(port):
    """检查CDP端口是否已有浏览器连接"""
    try:
        req = urllib.request.urlopen(f"http://localhost:{port}/json", timeout=2)
        return req.status == 200
    except:
        return False

def start_browser_with_cdp(browser_type, executable_path, cdp_port, user_data_dir):
    """启动浏览器并开启CDP"""
    os.makedirs(user_data_dir, exist_ok=True)

    if is_cdp_running(cdp_port):
        print(f"浏览器已通过CDP端口 {cdp_port} 连接")
        return True

    if browser_type == "firefox":
        args = [
            executable_path,
            "--remote-debugging-port",
            str(cdp_port),
            "-profile",
            user_data_dir,
        ]
    else:
        args = [
            executable_path,
            f"--remote-debugging-port={cdp_port}",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            f"--user-data-dir={user_data_dir}",
            "--no-first-run",
            "--no-default-browser-check",
        ]

    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    return True
