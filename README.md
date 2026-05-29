# calorie-notion-heatmap

每日热量摄入热力图，从 Notion「每日摄入」数据库读取「今日热量情况」函数属性，自动生成 GitHub 热力图并嵌入 Notion。

## 颜色说明

| 状态 | 颜色 |
|------|------|
| 暂无热量数据 | ⬜ 空白 `#E8EAED` |
| 热量严重超标 | 🔴 暗红 `#D97B7B` |
| 热量摄入略高 | 🟡 暖黄 `#D9B96E` |
| 热量摄入达标 | 🟢 柔绿 `#72A97A` |
| 热量摄入不足 | ⬜ 蓝灰 `#9BA8B0` |

## 项目结构

```
calorie-notion-heatmap/
├── update_calorie_heatmap.py   # 主脚本：拉取数据、生成 SVG、着色
├── archive_heatmap.py          # 归档脚本：生成历史年份 SVG
├── update_notion_embed.py      # 更新 Notion 嵌入链接（可选）
├── calorie.html                # 展示页面（支持深色模式、年份切换）
├── requirements.txt
├── calorie_heatmap/
│   └── main.svg                # 当年热力图（自动生成）
├── old_heatmap/
│   └── <year>.svg              # 历史年份热力图（归档）
└── .github/workflows/
    ├── calorie.yml             # 每日自动更新
    └── annual_heatmap.yml      # 每年 1 月 1 日自动归档
```

## 配置方法

### 1. GitHub Secrets

在仓库 Settings → Secrets and variables → Actions 中添加：

| Secret 名称 | 说明 |
|-------------|------|
| `NOTION_TOKEN` | Notion Integration Token |
| `NOTION_DATABASE_ID` | 「每日摄入」数据库 ID |
| `NOTION_PAGE` | （可选）热力图嵌入的 Notion 页面 URL/ID |

### 2. Notion 数据库要求

数据库需包含以下属性：
- **日期**（日期类型）：记录日期
- **今日热量情况**（公式/文本类型）：输出以下五种文本之一：
  - `暂无热量数据`
  - `热量严重超标`
  - `热量摄入略高`
  - `热量摄入达标`
  - `热量摄入不足`

### 3. 开启 GitHub Pages

仓库 Settings → Pages → Source 选择 `main` 分支，根目录。

展示页地址：`https://<username>.github.io/<repo>/calorie.html?image=<svg_raw_url>`

## 功能特性

- ✅ 每日自动更新（北京时间 23:00）
- ✅ 年度热力图归档（每年 1 月 1 日，支持手动指定年份）
- ✅ 深色模式自动感应 + 手动切换
- ✅ 年份切换下拉框
- ✅ 颜色图例展示
- ✅ 可选自动更新 Notion 嵌入链接
