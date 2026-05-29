import os
import datetime
import urllib.request
import urllib.error
import json
import sys


def get_github_raw_url(repository, ref, path):
    """构造 GitHub raw 文件 URL"""
    branch = ref.split("/")[-1] if ref else "main"
    return f"https://raw.githubusercontent.com/{repository}/{branch}/{path}"


def get_notion_heatmap_block(token, page_id):
    """在 Notion 页面中递归查找嵌入热力图的 image/embed 块，返回 block_id"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
    }

    def search_blocks(block_id):
        req = urllib.request.Request(
            f"https://api.notion.com/v1/blocks/{block_id}/children",
            headers=headers,
        )
        try:
            with urllib.request.urlopen(req) as response:
                results = json.loads(response.read()).get("results", [])
        except Exception as e:
            print(f"  ⚠️  读取块 {block_id} 失败: {e}")
            return None

        for child in results:
            btype = child.get("type")
            bid = child.get("id")

            if btype == "image":
                img_url = (
                    child.get("image", {}).get("external", {}).get("url", "")
                )
                if "calorie_heatmap" in img_url or "raw.githubusercontent.com" in img_url:
                    return bid

            elif btype == "embed":
                emb_url = child.get("embed", {}).get("url", "")
                if "calorie_heatmap" in emb_url or "raw.githubusercontent.com" in emb_url:
                    return bid

            if child.get("has_children"):
                found = search_blocks(bid)
                if found:
                    return found

        return None

    return search_blocks(page_id)


def update_notion_block(token, block_id, new_url):
    """将 Notion 的 image/embed 块更新为新的热力图 URL"""
    for block_type in ("image", "embed"):
        if block_type == "image":
            body = {"image": {"external": {"url": new_url}}}
        else:
            body = {"embed": {"url": new_url}}

        req = urllib.request.Request(
            f"https://api.notion.com/v1/blocks/{block_id}",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json",
            },
            method="PATCH",
        )
        try:
            with urllib.request.urlopen(req) as response:
                response.read()
            print(f"  ✅ 已更新 {block_type} 块 → {new_url}")
            return True
        except urllib.error.HTTPError as e:
            body_text = e.read().decode()
            if "validation_error" in body_text or "path_filter" in body_text:
                continue
            print(f"  ❌ 更新 {block_type} 块失败: {e} — {body_text}")
            return False
        except Exception as e:
            print(f"  ❌ 请求失败: {e}")
            return False

    return False


def extract_page_id(notion_url_or_id):
    """从 Notion URL 或纯 ID 中提取 32 位 page_id"""
    import re
    match = re.search(
        r"([a-f0-9]{32}|[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})",
        notion_url_or_id,
    )
    return match.group(0) if match else notion_url_or_id


def main():
    notion_token = os.getenv("NOTION_TOKEN")
    notion_page = os.getenv("NOTION_PAGE")  # 热力图所在的 Notion 页面 URL/ID
    repository = os.getenv("REPOSITORY")    # e.g. "username/calorie-notion-heatmap"
    ref = os.getenv("REF", "refs/heads/main")
    github_username = os.getenv("GITHUB_USERNAME", "")
    github_pages_repo = os.getenv("GITHUB_PAGES_REPO", "")  # GitHub Pages 仓库名（可选）

    if not notion_token:
        print("⚠️  未设置 NOTION_TOKEN，跳过 Notion 同步")
        return

    if not notion_page:
        print("⚠️  未设置 NOTION_PAGE，跳过 Notion 同步")
        return

    if not repository:
        print("⚠️  未设置 REPOSITORY，跳过 Notion 同步")
        return

    # 构造 SVG 的 raw GitHub URL
    svg_raw_url = get_github_raw_url(repository, ref, "calorie_heatmap/main.svg")

    # 包装进 GitHub Pages 展示页（如果仓库开启了 GitHub Pages）
    pages_repo = github_pages_repo or repository.split("/")[-1]
    username = github_username or repository.split("/")[0]
    heatmap_display_url = (
        f"https://{username}.github.io/{pages_repo}/calorie.html?image={svg_raw_url}"
    )

    print(f"🔗 热力图展示 URL: {heatmap_display_url}")

    # 在 Notion 页面中查找热力图块并更新
    page_id = extract_page_id(notion_page)
    print(f"🔍 正在 Notion 页面 {page_id} 中查找热力图块...")
    block_id = get_notion_heatmap_block(notion_token, page_id)

    if block_id:
        print(f"  找到热力图块: {block_id}")
        update_notion_block(notion_token, block_id, heatmap_display_url)
    else:
        print("  ⚠️  未找到热力图块，请在 Notion 页面中手动插入一个 embed 或 image 块，")
        print(f"       URL 填写: {heatmap_display_url}")


if __name__ == "__main__":
    main()
