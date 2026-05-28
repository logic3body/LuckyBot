"""
抽奖分类模块
"""

import json
import pathlib

from .fetcher import CLASSIFIED_DIR, LATEST_FILE


def parse_card_data(card_data: dict) -> dict:
    """从卡片数据中提取动态信息"""
    return {
        "type": card_data.get("type", ""),
        "dynamic_id": str(card_data.get("dynamic_id", "")),
        "uid": card_data.get("user", {}).get("uid", ""),
        "content": extract_card_content(card_data),
    }


def extract_card_content(card_data: dict) -> str:
    """从卡片数据中提取文字内容（支持新旧两种格式）"""
    # 新格式：直接有 summary 字段
    if "summary" in card_data:
        return card_data.get("summary", "")

    # 旧格式：需要解析 content 字段
    # 转发类型
    if card_data.get("type") == 1:
        origin = card_data.get("origin", {})
        origin_content = origin.get("content", [])
        if origin_content:
            return origin_content[0].get("text", "") if isinstance(origin_content, list) else str(origin_content)
        return ""

    # 图文类型
    if card_data.get("type") == 2:
        content = card_data.get("content", [])
        if isinstance(content, list) and content:
            return content[0].get("text", "") if isinstance(content[0], dict) else str(content[0])
        return ""

    # 纯文字类型
    if card_data.get("type") == 4:
        content = card_data.get("content", [])
        if isinstance(content, list) and content:
            return content[0].get("text", "") if isinstance(content[0], dict) else str(content[0])
        return ""

    return ""


def get_card_id(card_data: dict) -> str:
    """从卡片数据中获取动态 ID（支持新旧两种格式）"""
    # 新格式：直接有 id 字段
    if "id" in card_data:
        return str(card_data["id"])
    # 旧格式
    return str(card_data.get("all_dyn_id") or card_data.get("dynamic_id") or "")


def parse_classified_prizes(opus_info: dict) -> dict:
    """解析 opus 信息，分类提取奖品（用于旧版 opus 格式）"""
    categories = {
        "转发抽奖": [],
        "充电抽奖": [],
        "预约抽奖": [],
        "互动抽奖": [],
    }
    current_cat = None

    modules = opus_info.get("item", {}).get("modules", [])
    for mod in modules:
        if mod.get("module_type") != "MODULE_TYPE_CONTENT":
            continue

        content = mod.get("module_content", {})
        paragraphs = content.get("paragraphs", [])

        for para in paragraphs:
            para_type = para.get("para_type")
            text_nodes = para.get("text", {}).get("nodes", [])

            para_text = "".join(
                node.get("word", {}).get("words", "")
                for node in text_nodes
                if node.get("type") == "TEXT_NODE_TYPE_WORD"
            )

            found_cat = None
            for cat in categories:
                if para_text.strip() == cat:
                    found_cat = cat
                    break

            if found_cat:
                current_cat = found_cat
                continue

            if para_type == 5 and current_cat:
                items = para.get("list", {}).get("items", [])
                for item in items:
                    for node in item.get("nodes", []):
                        if node.get("type") == "TEXT_NODE_TYPE_RICH":
                            rich = node.get("rich", {})
                            name = rich.get("text", "")
                            url = rich.get("jump_url", "")
                            categories[current_cat].append({"name": name, "url": url})

    return categories


def save_classified_prizes(categories: dict):
    """保存分类后的奖品到 JSON 文件"""
    for cat_name, items in categories.items():
        if not items:
            continue
        file_path = CLASSIFIED_DIR / f"{cat_name.replace('抽奖', '')}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)


def get_opus_id(opus_info: dict) -> str:
    """从 opus info 中获取动态 ID"""
    return str(opus_info.get("item", {}).get("basic", {}).get("dynamic_id_str", ""))


def extract_opus_content(opus_info: dict) -> str:
    """从 opus info 中提取文字内容"""
    texts = []
    modules = opus_info.get("item", {}).get("modules", [])
    for mod in modules:
        if mod.get("module_type") == "MODULE_TYPE_CONTENT":
            content = mod.get("module_content", {})
            paragraphs = content.get("paragraphs", [])
            for para in paragraphs:
                text_nodes = para.get("text", {}).get("nodes", [])
                for node in text_nodes:
                    if node.get("type") == "TEXT_NODE_TYPE_WORD":
                        words = node.get("word", {}).get("words", "")
                        texts.append(words)
    return "".join(texts)


def extract_author_uid(opus_info: dict) -> int:
    """从 opus info 中提取作者 UID"""
    modules = opus_info.get("item", {}).get("modules", {})

    # modules 是 dict 格式（新 API）
    if isinstance(modules, dict):
        author = modules.get("module_author", {})
        mid = author.get("mid", 0)
        if mid:
            return mid
        return author.get("user", {}).get("mid", 0)

    # modules 是 list 格式（旧 API）
    if isinstance(modules, list):
        for mod in modules:
            if mod.get("module_type") == "MODULE_TYPE_AUTHOR":
                author = mod.get("module_author", {})
                return author.get("mid", 0) or author.get("user", {}).get("mid", 0)

    return 0


def classify_dynamics(dynamics: list) -> dict:
    """从动态列表中分类抽奖类型，提取每个分类下的具体抽奖链接

    Returns:
        dict: {"forward": [], "charge": [], "subscribe": [], "interact": []}
    """
    result = {
        "forward": [],
        "charge": [],
        "subscribe": [],
        "interact": [],
    }

    # 分类名到 key 的映射
    cat_map = {
        "转发抽奖": "forward",
        "充电抽奖": "charge",
        "预约抽奖": "subscribe",
        "互动抽奖": "interact",
    }

    for opus_info in dynamics:
        # 提取作者 UID
        author_uid = extract_author_uid(opus_info)

        categories = parse_classified_prizes(opus_info)
        for cat_name, items in categories.items():
            if items:
                cat_key = cat_map.get(cat_name)
                if cat_key:
                    # 为每个项目添加作者 UID
                    for item in items:
                        item["author_uid"] = author_uid
                    result[cat_key].extend(items)

    return result