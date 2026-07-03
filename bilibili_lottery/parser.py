"""
内容解析模块
"""

import re


def extract_dynamic_id(url: str) -> str:
    """从 URL 中提取动态 ID"""
    match = re.search(r'/(\d+)', url)
    if match:
        return match.group(1)
    return ""


def extract_opus_links(opus_info: dict) -> list:
    """从 opus_info 中提取所有抽奖相关链接

    适用于无分类的汇总账号动态（如 你的抽奖工具人），
    直接从内容中提取所有 bilibili 动态/opus 链接。

    Args:
        opus_info: opus.get_info() 返回的数据

    Returns:
        list[dict]: [{"name": str, "url": str}, ...]
    """
    items = []
    seen_urls = set()
    modules = opus_info.get("item", {}).get("modules", [])

    for mod in modules:
        if mod.get("module_type") != "MODULE_TYPE_CONTENT":
            continue

        content = mod.get("module_content", {})
        paragraphs = content.get("paragraphs", [])

        for para in paragraphs:
            # 从 text.nodes 中提取 RICH 节点的链接
            text_nodes = (para.get("text") or {}).get("nodes", [])
            for node in text_nodes:
                if node.get("type") != "TEXT_NODE_TYPE_RICH":
                    continue
                rich = node.get("rich", {})
                url = rich.get("jump_url", "")
                if not url:
                    continue
                # 只保留抽奖相关链接
                if not re.search(r'(t\.bilibili\.com/|bilibili\.com/opus/)', url):
                    continue
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                name = rich.get("text", "") or ""
                # 清理 URL 中的追踪参数
                clean_url = url.split("?")[0] if "?" in url else url
                items.append({"name": name, "url": clean_url})

            # 从 list.items 中提取 RICH 节点的链接（编号列表格式）
            list_items = (para.get("list") or {}).get("items", [])
            for li in list_items:
                for node in li.get("nodes", []):
                    if node.get("type") != "TEXT_NODE_TYPE_RICH":
                        continue
                    rich = node.get("rich", {})
                    url = rich.get("jump_url", "")
                    if not url:
                        continue
                    if not re.search(r'(t\.bilibili\.com/|bilibili\.com/opus/)', url):
                        continue
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    name = rich.get("text", "") or ""
                    clean_url = url.split("?")[0] if "?" in url else url
                    items.append({"name": name, "url": clean_url})

    return items


def parse_forward_requirements(text: str) -> dict:
    """
    从转发抽奖的文字要求中解析需要执行的操作

    Args:
        text: 抽奖要求的文字内容

    Returns:
        dict: {"follow": bool, "repost": bool, "comment": bool, "like": bool}
    """
    requirements = {
        "follow": False,
        "repost": False,
        "comment": False,
        "like": False,
    }

    # 检测关注
    if "关注" in text:
        requirements["follow"] = True

    # 检测转发
    if "转发" in text:
        requirements["repost"] = True

    # 检测评论
    if "评论" in text:
        requirements["comment"] = True

    # 检测点赞
    if "点赞" in text:
        requirements["like"] = True

    return requirements