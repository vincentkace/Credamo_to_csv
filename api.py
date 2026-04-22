import requests
import pandas as pd
import json

def get_page_df(cookie_str, survey_id, page_size, page_num, download=False):
    """获取单页问卷数据

    Args:
        cookie_str: cookie字符串
        survey_id: 项目ID
        page_size: 每页条数
        page_num: 页码
        download: 是否为下载模式（下载模式不替换列名）

    Returns:
        tuple: (DataFrame, total_cnt) 或 (DataFrame, total_cnt, ques_headers_kv, ques_headers)
    """
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
        "referer": f"https://www.credamo.com/survey.html?surveyId={survey_id}",
        "cookie": cookie_str,
        "content-type": "application/json"
    }

    url = "https://www.credamo.com/v1/cleanVar/dataOverview"

    try:
        resp = requests.post(
            url=url,
            headers=headers,
            params={"currPageSize": page_size, "currPageIndex": page_num},
            json={"surveyId": survey_id},
            verify=False
        )
        if resp.status_code == 200:
            output = resp.json()
            if output.get("success") and output.get("data"):
                data = output['data']
                ques_headers = data.get('header', [])
                row_list = data.get('rowList', [])
                total_cnt = data.get('total', 0)

                # 如果total为0但有数据，使用实际行数作为参考
                if total_cnt == 0 and len(row_list) > 0:
                    total_cnt = len(row_list)  # 至少获取当前页的行数

                # 构建列ID到问题名称的映射
                ques_headers_kv = {}
                for header in ques_headers:
                    q_num = header.get('qNum', '')
                    q_name = header.get('questionName', '')
                    header_id = header["id"]
                    if q_num and q_name:
                        ques_headers_kv[header_id] = f"{q_num} {q_name}"
                    elif q_name:
                        ques_headers_kv[header_id] = q_name
                    else:
                        ques_headers_kv[header_id] = header_id

                df = pd.DataFrame(data.get('rowList', []))

                if not download:
                    # 替换列名为问题名称
                    df.columns = [
                        ques_headers_kv.get(id, id) if id not in ['status', 'answerId', 'userId'] else id
                        for id in df.columns
                    ]
                    return df, total_cnt
                else:
                    return df, total_cnt, ques_headers_kv, ques_headers
            else:
                print(f"API返回错误: {output.get('msg', '未知错误')}")
                return pd.DataFrame(), 0
        else:
            print(f"API请求失败: {resp.status_code}")
            return pd.DataFrame(), 0
    except Exception as e:
        print(f"API请求异常: {e}")
        return pd.DataFrame(), 0


def download_all_data(cookie_str, survey_id, page_size=10):
    """下载所有页数据

    Args:
        cookie_str: cookie字符串
        survey_id: 项目ID
        page_size: 每页条数（默认10，但会自动尝试获取更大值来获取准确总数）

    Returns:
        DataFrame: 合并后的数据
    """
    # 先用200获取第一页来获取总数
    df, total_cnt, ques_headers_kv, ques_headers = get_page_df(
        cookie_str, survey_id, 200, 1, download=True
    )

    # 如果total为0，使用实际行数
    if total_cnt == 0:
        total_cnt = len(df)

    # 如果总数小于等于200，一页就能获取完
    if total_cnt <= 200:
        total_page_num = 1
        all_dfs = [df]
    else:
        # 总数大于200，需要分页获取
        page_size = 200
        total_page_num = (total_cnt + page_size - 1) // page_size
        all_dfs = [df]

        for page_num in range(2, total_page_num + 1):
            print(f"下载第 {page_num}/{total_page_num} 页")
            df, total_cnt, ques_headers_kv, _ = get_page_df(
                cookie_str, survey_id, page_size, page_num, download=True
            )
            if 'userId' in df.columns and len(df) > 0:
                all_dfs.append(df)

    if len(all_dfs) == 0 or len(all_dfs[0]) == 0:
        print("没有数据")
        return pd.DataFrame()

    # 合并所有页数据
    page_dfs = pd.concat(all_dfs, ignore_index=True)

    # 替换列名
    page_dfs.columns = [
        ques_headers_kv.get(id, id) if id not in ['status', 'answerId', 'userId'] else id
        for id in page_dfs.columns
    ]

    # 剔除已拒绝的（检查任何列是否包含*）
    # 如果某行有任何列的值是"*"，则表示被拒绝
    has_star = (page_dfs == "*").any(axis=1)
    page_dfs = page_dfs[~has_star]

    # 调整列顺序 - 先获取实际存在的列名
    base_cols = ['status', 'answerId', 'userId']
    extra_cols = [ques_headers_kv.get(h['id'], h['id']) for h in ques_headers if h['id'] in page_dfs.columns]
    final_cols = [c for c in base_cols if c in page_dfs.columns] + [c for c in extra_cols if c in page_dfs.columns]

    # 如果还有不在上述列表中的列，也加进去
    for col in page_dfs.columns:
        if col not in final_cols:
            final_cols.append(col)

    page_dfs = page_dfs[final_cols]

    return page_dfs


def save_to_file(df, filename):
    """保存数据到文件，支持xlsx和csv格式"""
    if filename.endswith('.xlsx'):
        df.to_excel(filename, index=False)
    else:
        df.to_csv(filename, index=False, encoding='utf-8-sig')
