use serde::{Deserialize, Serialize};
use tauri::Emitter;
use std::collections::HashMap;

#[derive(Debug, Serialize, Deserialize, Clone)]
struct HeaderInfo {
    id: String,
    question_name: String,
}

#[derive(Debug, Serialize, Deserialize)]
struct DownloadResult {
    success: bool,
    message: String,
    total: usize,
    filename: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
struct CredamoResponse {
    success: bool,
    data: Option<CredamoData>,
    msg: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
struct CredamoData {
    header: Vec<HeaderItem>,
    #[serde(rename = "rowList", alias = "row_list")]
    row_list: Vec<serde_json::Value>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
struct HeaderItem {
    id: String,
    #[serde(rename = "questionName")]
    question_name: String,
}

fn parse_cookies(text: &str) -> HashMap<String, String> {
    let mut cookies = HashMap::new();
    for line in text.lines() {
        let line = line.trim();
        if line.is_empty() || line.to_lowercase().starts_with("name") {
            continue;
        }
        if line.contains('\t') {
            let parts: Vec<&str> = line.split('\t').collect();
            if parts.len() >= 2 {
                let name = parts[0].trim();
                let value = parts[1].trim();
                if !name.is_empty() && !value.is_empty() {
                    cookies.insert(name.to_string(), value.to_string());
                }
            }
        } else if line.contains('=') && !line.contains(':') {
            if let Some((k, v)) = line.split_once('=') {
                let k = k.trim();
                let v = v.trim();
                if !k.is_empty() && !v.is_empty() {
                    cookies.insert(k.to_string(), v.to_string());
                }
            }
        }
    }
    cookies
}

fn get_field_name(h: &HeaderItem) -> String {
    let field_id = &h.id;
    let question_name = &h.question_name;

    let field_map: HashMap<&str, &str> = [
        ("answerSign", "答案ID"),
        ("userSign", "用户ID"),
        ("answerStartTime", "开始时间"),
        ("answerEndTime", "结束时间"),
        ("answerTime", "耗时(秒)"),
        ("sourceType", "答题渠道"),
        ("dispenseId", "发布ID"),
        ("dispenseName", "发布名称"),
        ("fromIp", "IP地址"),
        ("lng", "经度"),
        ("lat", "纬度"),
        ("country", "国家"),
        ("province", "省份"),
        ("city", "城市"),
        ("deviceType", "设备类型"),
        ("osType", "操作系统"),
        ("browserType", "浏览器"),
        ("resolution", "屏幕分辨率"),
        ("randomElements", "随机元素"),
        ("userId", "用户ID"),
        ("answerId", "答案ID"),
        ("status", "状态"),
    ]
    .into_iter()
    .collect();

    if let Some(name) = field_map.get(field_id.as_str()) {
        return name.to_string();
    }
    if !question_name.is_empty() {
        return question_name.clone();
    }
    field_id.clone()
}

#[tauri::command]
async fn download_data(
    cookie_text: String,
    survey_id: String,
    log_callback: tauri::AppHandle,
) -> Result<DownloadResult, String> {
    log_callback.emit("log", "🚀 开始请求问卷 ".to_string() + &survey_id).ok();

    let cookies = parse_cookies(&cookie_text);
    if cookies.is_empty() {
        return Ok(DownloadResult {
            success: false,
            message: "未解析到任何Cookie".to_string(),
            total: 0,
            filename: None,
        });
    }

    let cookie_header: String = cookies
        .iter()
        .map(|(k, v)| format!("{}={}", k, v))
        .collect::<Vec<_>>()
        .join("; ");

    let client = reqwest::Client::new();
    let base_url = "https://www.credamo.com/v1/cleanVar/dataOverview";
    let mut all_data: Vec<CredamoData> = Vec::new();
    let mut page = 1;
    let mut total = 0;

    loop {
        let url = format!("{}?currPageSize=200&currPageIndex={}", base_url, page);
        
        log_callback.emit("log", format!("📥 正在拉取第 {} 页...", page)).ok();

        let body = serde_json::json!({
            "surveyId": survey_id
        });

        let response = client
            .post(&url)
            .header("cookie", &cookie_header)
            .header("content-type", "application/json")
            .header("user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            .json(&body)
            .send()
            .await;

        match response {
            Ok(resp) => {
                log_callback.emit("log", format!("  状态码: {}", resp.status())).ok();

                if resp.status() == reqwest::StatusCode::OK {
                    let text = resp.text().await.map_err(|e| e.to_string())?;
                    log_callback.emit("log", format!("  响应长度: {} bytes", text.len())).ok();
                    
                    match serde_json::from_str::<CredamoResponse>(&text) {
                        Ok(data) => {
                            if data.success {
                                if let Some(resp_data) = data.data {
                                    let row_count = resp_data.row_list.len();
                                    total += row_count;
                                    all_data.push(resp_data.clone());
                                    log_callback.emit("log", format!("✅ 第{}页: {}条 (累计:{})", page, row_count, total)).ok();

                                    if row_count < 200 {
                                        log_callback.emit("log", "🏁 数据拉取完毕".to_string()).ok();
                                        break;
                                    }
                                    page += 1;
                                } else {
                                    log_callback.emit("log", "❌ 无数据".to_string()).ok();
                                    break;
                                }
                            } else {
                                let msg = data.msg.unwrap_or_else(|| "未知错误".to_string());
                                log_callback.emit("log", format!("❌ 业务错误: {}", msg)).ok();
                                break;
                            }
                        }
                        Err(e) => {
                            log_callback.emit("log", format!("❌ JSON解析错误: {}", e)).ok();
                            let preview = if text.len() > 500 { &text[..500] } else { &text };
                            log_callback.emit("log", format!("  响应内容: {}", preview)).ok();
                            break;
                        }
                    }
                } else if resp.status() == reqwest::StatusCode::UNAUTHORIZED {
                    log_callback.emit("log", "❌ 401 未授权: Cookie已过期或无效".to_string()).ok();
                    return Ok(DownloadResult {
                        success: false,
                        message: "Cookie已过期或无效".to_string(),
                        total,
                        filename: None,
                    });
                } else {
                    log_callback.emit("log", format!("❌ HTTP错误: {}", resp.status())).ok();
                    break;
                }
            }
            Err(e) => {
                log_callback.emit("log", format!("❌ 请求异常: {}", e)).ok();
                break;
            }
        }
    }

    if all_data.is_empty() || total == 0 {
        return Ok(DownloadResult {
            success: false,
            message: "未获取到任何数据".to_string(),
            total: 0,
            filename: None,
        });
    }

    let headers = &all_data[0].header;
    let cols: Vec<String> = std::iter::once("userId".to_string())
        .chain(std::iter::once("answerId".to_string()))
        .chain(std::iter::once("status".to_string()))
        .chain(headers.iter().map(|h| get_field_name(h)))
        .collect();

    let timestamp = chrono_lite_timestamp();
    let filename = format!("credamo_{}_{}.csv", survey_id, timestamp);

    let filepath = std::path::PathBuf::from(&filename);

    let mut wtr = csv::Writer::from_path(&filepath).map_err(|e| e.to_string())?;

    wtr.write_record(&cols).map_err(|e| e.to_string())?;

    for data in &all_data {
        for row in &data.row_list {
            let mut row_data = vec![
                row.get("userId").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                row.get("answerId").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                row.get("status").and_then(|v| v.as_str()).unwrap_or("").to_string(),
            ];
            for h in headers {
                let val = row.get(&h.id).map(|v| {
                    match v {
                        serde_json::Value::String(s) => s.clone(),
                        _ => v.to_string(),
                    }
                }).unwrap_or_default();
                row_data.push(val);
            }
            wtr.write_record(&row_data).map_err(|e| e.to_string())?;
        }
    }

    wtr.flush().map_err(|e| e.to_string())?;

    log_callback.emit("log", format!("💾 已保存: {}", filepath.display())).ok();

    Ok(DownloadResult {
        success: true,
        message: "下载成功".to_string(),
        total,
        filename: Some(filename),
    })
}

fn chrono_lite_timestamp() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let duration = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default();
    let secs = duration.as_secs();
    let now = secs + 8 * 3600;
    let hours = (now % 86400) / 3600;
    let mins = (now % 3600) / 60;
    let s = now % 60;
    let days = now / 86400;
    let mut year = 1970;
    let mut remaining_days = days as i64;
    loop {
        let days_in_year = if is_leap_year(year) { 366 } else { 365 };
        if remaining_days < days_in_year {
            break;
        }
        remaining_days -= days_in_year;
        year += 1;
    }
    let months_days = if is_leap_year(year) {
        [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    } else {
        [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    };
    let mut month = 1;
    for d in months_days.iter() {
        if remaining_days < *d as i64 {
            break;
        }
        remaining_days -= *d as i64;
        month += 1;
    }
    let day = remaining_days + 1;
    format!("{}{:02}{:02}_{:02}{:02}{:02}", year, month, day, hours, mins, s)
}

fn is_leap_year(year: i64) -> bool {
    (year % 4 == 0 && year % 100 != 0) || (year % 400 == 0)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![download_data])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}