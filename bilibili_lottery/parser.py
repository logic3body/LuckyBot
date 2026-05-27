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

    # 检测关注 (关注/关)
    if "关注" in text or "关" in text:
        requirements["follow"] = True

    # 检测转发 (转发/转)
    if "转发" in text or "转" in text:
        requirements["repost"] = True

    # 检测评论 (评论/评)
    if "评论" in text or "评" in text:
        requirements["comment"] = True

    # 检测点赞 (点赞/赞)
    if "点赞" in text or "赞" in text:
        requirements["like"] = True

    return requirements