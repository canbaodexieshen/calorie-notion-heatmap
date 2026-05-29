"""年度热量摄入热力图归档脚本

用于 GitHub Actions 每年 1 月 1 日自动执行（也可手动触发）。
将指定年份的热力图生成并存入 old_heatmap/ 目录，
供 calorie.html 的年份切换下拉框调用。
"""

import os
import sys

# 导入主脚本中的函数
import update_calorie_heatmap as uch


def filter_data_by_year(data_dict, year):
    """从全量数据中筛选出指定年份的记录"""
    year_prefix = str(year)
    return {k: v for k, v in data_dict.items() if k.startswith(year_prefix)}


def main():
    notion_token = os.getenv("NOTION_TOKEN")
    database_id = os.getenv("NOTION_DATABASE_ID")

    if not notion_token or not database_id:
        print("❌ 缺少必要的环境变量：NOTION_TOKEN 或 NOTION_DATABASE_ID")
        sys.exit(1)

    target_year = int(os.getenv("TARGET_YEAR", "0"))
    if target_year == 0:
        print("❌ TARGET_YEAR 未设置")
        sys.exit(1)

    print(f"📅 正在为 {target_year} 年生成归档热力图...")

    # ① 拉取 Notion 全量数据
    all_data = uch.get_notion_data(notion_token, database_id)

    # ② 筛选目标年份数据（用于正确的年度总计）
    year_data = filter_data_by_year(all_data, target_year)
    year_counts = uch.get_year_summary(year_data, target_year)
    达标天数 = year_counts.get("热量摄入达标", 0)
    summary_str = f"{达标天数}天达标"
    print(f"📊 {target_year} 年统计：{year_counts}")

    # ③ 生成底稿 SVG（由 github_heatmap CLI 按年份过滤）
    svg_path = uch.generate_heatmap(notion_token, database_id, target_year)

    if not os.path.exists(svg_path):
        print(f"❌ 底稿 SVG 未生成，路径不存在: {svg_path}")
        sys.exit(1)

    # ④ 热量状态着色 + 统计注入（传入 summary_str 确保左上角显示正确的年度总计）
    print("🎨 正在执行热量状态着色与统计注入...")
    uch.process_svg_styling(
        svg_path,
        all_data,               # 全量数据用于逐日着色
        target_year,
        total_override=summary_str,  # 年度统计只计算目标年份
    )

    # ⑤ 移动到 old_heatmap/<year>.svg
    os.makedirs("old_heatmap", exist_ok=True)
    dest = f"old_heatmap/{target_year}.svg"
    os.replace(svg_path, dest)
    print(f"✅ 归档完成：{dest}")

    # ⑥ 清理旧占位文件
    test_file = "old_heatmap/test"
    if os.path.exists(test_file):
        os.remove(test_file)
        print(f"🧹 已清理占位文件：{test_file}")


if __name__ == "__main__":
    main()
