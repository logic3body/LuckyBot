"""
通知检测模块 - 检测是否中奖
"""

import asyncio
import json
from datetime import datetime

from bilibili_api import Credential
from bilibili_api.session import get_at

from .utils import serverchan_push, log_winning, load_notified_winnings, add_notified_winning

LOTTERY_KEYWORDS = ["恭喜", "中奖", "获奖", "抽中"]


async def check_cookie_valid(credential: Credential) -> bool:
    """
    检查 Cookie 是否有效

    Args:
        credential: 登录凭证

    Returns:
        bool: Cookie 是否有效
    """
    return await credential.check_valid()


async def check_lottery_winning(credential: Credential, keywords: list = None) -> list:
    """
    检查 @我 通知列表，返回可能中奖的通知（仅返回未推送过的）

    Args:
        credential: 登录凭证
        keywords: 关键词列表，默认 LOTTERY_KEYWORDS

    Returns:
        list: 可能中奖的通知列表（仅新通知）
    """
    if keywords is None:
        keywords = LOTTERY_KEYWORDS

    results = []
    notified_ids = load_notified_winnings()

    try:
        # 获取 @我的通知
        notifications = await get_at(credential)

        # 遍历通知
        items = notifications.get("items", [])
        for item in items:
            # 获取通知 ID
            item_id = item.get("id")
            if item_id and item_id in notified_ids:
                continue  # 已推送过，跳过

            # 解析内容 - 来源于 item.source_content
            content = item.get("item", {}).get("source_content", "")
            source_url = item.get("item", {}).get("uri", "") or item.get("item", {}).get("native_uri", "")
            sender_name = item.get("user", {}).get("nickname", "未知")
            ctime = item.get("at_time", 0)

            # 关键词匹配
            for kw in keywords:
                if kw in content:
                    result = {
                        "id": item_id,
                        "source": sender_name,
                        "content": content,
                        "url": source_url,
                        "time": datetime.fromtimestamp(ctime).strftime("%Y-%m-%d %H:%M:%S") if ctime else "",
                        "keyword": kw,
                    }
                    results.append(result)
                    # 标记为已通知
                    if item_id:
                        add_notified_winning(item_id)
                    break  # 匹配到一个关键词就够，不重复添加

    except Exception as e:
        print(f"获取通知失败: {e}")

    return results


def print_winning_notifications(results: list):
    """打印中奖通知结果"""
    if not results:
        print("未检测到可能的中奖通知")
        return

    print(f"\n检测到 {len(results)} 条可能的中奖通知:\n")
    for i, item in enumerate(results, 1):
        print(f"=== 可能的的中奖 {i} ===")
        print(f"- 来源: {item['source']}")
        print(f"- 内容: {item['content']}")
        print(f"- 链接: {item['url']}")
        print(f"- 时间: {item['time']}")
        print(f"- 命中关键词: {item['keyword']}")
        print("---")

    print()


async def main():
    """测试用主函数"""
    import importlib

    try:
        user_config = importlib.import_module("config")
    except ModuleNotFoundError:
        print("请先创建 config.py 文件")
        return

    cred = Credential(**user_config.CREDENTIAL)
    uid = getattr(user_config, 'TARGET_UID', None)

    print("正在检测通知...")
    results = await check_lottery_winning(cred, uid=uid)
    print_winning_notifications(results)


if __name__ == "__main__":
    asyncio.run(main())