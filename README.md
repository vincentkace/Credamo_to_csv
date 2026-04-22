# Credamo_to_csv
Download questionaire data from Credamo platform.

## 安装依赖

```bash
pip install playwright pandas requests
```

## 运行


手动启动Chrome：
```
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --disable-blink-features=AutomationControlled --disable-infobars --user-data-dir="C:\Users\k8723\work\CredamoDataDownloader\Credamo_to_csv\browser_data"
```

然后在另一个终端运行：
```
python main.py
```