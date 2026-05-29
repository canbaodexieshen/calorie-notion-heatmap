import os
import subprocess
import datetime
import re
import sys
import urllib.request
import json


# ==================== 颜色映射配置 ====================
# 五种热量状态对应颜色
CALORIE_COLORS = {
    "暂无热量数据": None,
    "热量严重超标": "#fa2f47",   # 鲜红
    "热量摄入略高": "#ff8400",   # 橙黄
    "热量摄入达标": "#1ed760",   # 亮绿（Spotify绿）
    "热量摄入不足": "#90b1fb",   # 柔和蓝色
}

# 空白格颜色（无数据）
COLOR_EMPTY = "#E8EAED"


def get_notion_data(token, database_id):
    """从 Notion 每日摄入数据库拉取所有页面，提取日期、今日热量情况和总卡路里计算。
    
    返回两个字典：
      status_dict  {date_str: calorie_status}   热量状态
      kcal_dict    {date_str: kcal_value}        当天总卡路里（数值，kcal）
    """
    print("🔍 正在连接 Notion 数据库并抓取热量摄入数据...")
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

    status_dict = {}
    kcal_dict = {}
    has_more = True
    next_cursor = None

    while has_more:
        body = {}
        if next_cursor:
            body["start_cursor"] = next_cursor
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as response:
                res = json.loads(response.read())
                for result in res.get("results", []):
                    props = result.get("properties", {})

                    # 读取"日期"属性（date 类型）
                    date_val = None
                    if props.get("日期") and props["日期"].get("date"):
                        date_val = props["日期"]["date"].get("start")

                    if not date_val:
                        continue
                    date_str = str(date_val).split("T")[0]

                    # 读取"今日热量情况"属性（formula 输出 string 类型）
                    calorie_status = None
                    status_prop = props.get("今日热量情况")
                    if status_prop:
                        ptype = status_prop.get("type")
                        if ptype == "formula":
                            f_data = status_prop.get("formula", {})
                            if f_data.get("type") == "string":
                                calorie_status = f_data.get("string", "").strip()
                        elif ptype == "rich_text":
                            rt = status_prop.get("rich_text", [])
                            if rt:
                                calorie_status = rt[0].get("plain_text", "").strip()
                        elif ptype == "select":
                            sel = status_prop.get("select")
                            if sel:
                                calorie_status = sel.get("name", "").strip()

                    if calorie_status:
                        # 优先级：超标 > 略高 > 达标 > 不足 > 无数据
                        existing = status_dict.get(date_str, "暂无热量数据")
                        priority = ["暂无热量数据", "热量摄入不足", "热量摄入达标", "热量摄入略高", "热量严重超标"]
                        if priority.index(calorie_status) > priority.index(existing):
                            status_dict[date_str] = calorie_status

                    # 读取"总卡路里计算"属性（formula / number 类型）
                    kcal_prop = props.get("总卡路里计算")
                    if kcal_prop:
                        ptype = kcal_prop.get("type")
                        kcal_val = None
                        if ptype == "formula":
                            f_data = kcal_prop.get("formula", {})
                            if f_data.get("type") == "number":
                                kcal_val = f_data.get("number")
                            elif f_data.get("type") == "string":
                                # 有时 formula 返回字符串，提取数字
                                m = re.search(r"(\d+(\.\d+)?)", str(f_data.get("string", "")))
                                kcal_val = float(m.group(1)) if m else None
                        elif ptype == "number":
                            kcal_val = kcal_prop.get("number")
                        elif ptype == "rollup":
                            r_data = kcal_prop.get("rollup", {})
                            if r_data.get("type") == "number":
                                kcal_val = r_data.get("number")

                        if kcal_val is not None:
                            # 多条记录同一天时累加
                            kcal_dict[date_str] = kcal_dict.get(date_str, 0) + kcal_val

                has_more = res.get("has_more", False)
                next_cursor = res.get("next_cursor")
        except Exception as e:
            print(f"❌ 获取 Notion 数据失败: {e}")
            sys.exit(1)

    valid_count = sum(1 for v in status_dict.values() if v != "暂无热量数据")
    print(f"✅ 共读取到 {len(status_dict)} 天记录，其中 {valid_count} 天有有效热量数据")
    return status_dict, kcal_dict


def get_color_for_status(status):
    """根据热量状态返回对应颜色（空白/红/黄/绿/灰）"""
    if not status or status == "暂无热量数据":
        return COLOR_EMPTY
    return CALORIE_COLORS.get(status, COLOR_EMPTY)


def get_status_display(status):
    """获取状态的展示文本"""
    if not status or status == "暂无热量数据":
        return "暂无数据"
    return status


def get_year_summary(data_dict, year):
    """统计指定年份各状态的天数"""
    counts = {
        "热量严重超标": 0,
        "热量摄入略高": 0,
        "热量摄入达标": 0,
        "热量摄入不足": 0,
    }
    year_prefix = str(year)
    for date_str, status in data_dict.items():
        if date_str.startswith(year_prefix) and status in counts:
            counts[status] += 1
    return counts


def build_summary_str(year_counts):
    """根据各状态天数生成标题统计字符串"""
    达标 = year_counts.get("热量摄入达标", 0)
    超标 = year_counts.get("热量严重超标", 0)
    略高 = year_counts.get("热量摄入略高", 0)
    不足 = year_counts.get("热量摄入不足", 0)
    return f"{达标}天达标 · {超标}天超标 · {略高}天略高 · {不足}天不足"


def process_svg_styling(file_path, status_dict, kcal_dict, current_year, total_override=None):
    """对底稿 SVG 执行热量状态着色，并修正年度统计文字。
    若提供 total_override，则用它覆盖左上角统计值（用于年度归档场景）。
    
    参数：
      status_dict   {date_str: calorie_status}
      kcal_dict     {date_str: kcal_value}
      total_override  归档场景传入的已拼好的摘要字符串
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. 修正统计文字
    year_counts = get_year_summary(status_dict, current_year)

    if total_override is not None:
        summary_str = total_override
    else:
        summary_str = build_summary_str(year_counts)

    content = re.sub(
        rf"({current_year}:\s*)[^\n<]+",
        rf"\g<1>{summary_str}",
        content,
    )

    # 2. 对每个日期格子应用热量状态颜色，并在 title 中追加卡路里数值
    def rect_replacer(match):
        rect_tag = match.group(0)
        date_match = re.search(r"<title>(\d{4}-\d{2}-\d{2})", rect_tag)
        if not date_match:
            return rect_tag

        date_str = date_match.group(1)
        status = status_dict.get(date_str, "暂无热量数据")
        color = get_color_for_status(status)
        display_text = get_status_display(status)

        # 追加卡路里数值到 tooltip
        kcal = kcal_dict.get(date_str)
        if kcal is not None:
            kcal_int = int(round(kcal))
            tooltip = f"{date_str} - {display_text} ({kcal_int} kcal)"
        else:
            tooltip = f"{date_str} - {display_text}"

        rect_tag = re.sub(
            r"<title>\d{4}-\d{2}-\d{2}</title>",
            f"<title>{tooltip}</title>",
            rect_tag,
            count=1
        )

        return re.sub(r'fill="[^"]+"', f'fill="{color}"', rect_tag, count=1)

    content = re.sub(
        r'<rect\b[^>]*><title>.*?</title></rect>',
        rect_replacer,
        content,
        flags=re.DOTALL,
    )

    # 3. 补充白色背景
    if 'id="background"' not in content:
        content = content.replace("<svg ", '<svg style="background-color:white;" ', 1)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"🎨 着色完成：{year_counts}")


def generate_heatmap(notion_token, database_id, year, me_name=None):
    """调用 github_heatmap CLI 生成底稿 SVG，返回输出路径"""
    if me_name is None:
        me_name = os.getenv("HEATMAP_NAME", "热量摄入热力图")

    command = [
        "github_heatmap",
        "notion",
        "--notion_token", notion_token,
        "--database_id", database_id,
        "--date_prop_name", "日期",
        "--value_prop_name", "今日热量情况",
        "--unit", "",
        "--year", str(year),
        "--me", me_name,
        "--without-type-name",
        "--background-color", "#FFFFFF",
        "--track-color", COLOR_EMPTY,
        "--dom-color", COLOR_EMPTY,
        "--text-color", "#000000",
    ]

    print(f"🚀 正在调用热力图引擎生成 {year} 年底稿...")
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)

    return "OUT_FOLDER/notion.svg"


def main():
    notion_token = os.getenv("NOTION_TOKEN")
    database_id = os.getenv("NOTION_DATABASE_ID")

    if not notion_token or not database_id:
        print("❌ 缺少必要的环境变量：NOTION_TOKEN 或 NOTION_DATABASE_ID")
        sys.exit(1)

    current_year = datetime.datetime.now().year
    target_year = int(os.getenv("YEAR", current_year))

    # ① 拉取 Notion 数据（返回 status_dict 和 kcal_dict）
    real_status, real_kcal = get_notion_data(notion_token, database_id)

    # ② 生成底稿 SVG
    svg_path = generate_heatmap(notion_token, database_id, target_year)

    if not os.path.exists(svg_path):
        print(f"❌ 底稿 SVG 未生成，路径不存在: {svg_path}")
        sys.exit(1)

    # ③ 热量状态着色 + 统计注入
    print("🎨 正在执行热量状态着色与统计注入...")
    process_svg_styling(svg_path, real_status, real_kcal, target_year)

    # ④ 移动到 calorie_heatmap/main.svg
    os.makedirs("calorie_heatmap", exist_ok=True)
    dest = "calorie_heatmap/main.svg"
    os.replace(svg_path, dest)
    print(f"🎉 热力图已保存至 {dest}")


if __name__ == "__main__":
    main()
