"""
抽奖参与模块
"""

import asyncio
import random

from bilibili_api import Credential, dynamic, user
from bilibili_api.comment import send_comment, CommentResourceType

from .utils import log_action


async def follow_user(uid: int, credential: Credential, max_retries: int = 3) -> bool:
    """关注用户，返回是否成功（已关注也算成功）"""
    for attempt in range(max_retries):
        try:
            u = user.User(uid=uid, credential=credential)
            await u.modify_relation(user.RelationType.SUBSCRIBE)
            log_action("follow", "", uid, "success")
            return True
        except Exception as e:
            if "22014" in str(e):
                log_action("follow", "", uid, "success", "already_followed")
                return True
            if attempt < max_retries - 1:
                wait = random.uniform(2, 4)
                await asyncio.sleep(wait)
            else:
                log_action("follow", "", uid, "failed", str(e))
                raise


async def repost_dynamic(dynamic_id: str, credential: Credential, max_retries: int = 3) -> bool:
    """转发动态"""
    for attempt in range(max_retries):
        try:
            d = dynamic.Dynamic(dynamic_id=dynamic_id, credential=credential)
            await d.repost()
            log_action("repost", dynamic_id, None, "success")
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                wait = random.uniform(3, 5)
                await asyncio.sleep(wait)
            else:
                log_action("repost", dynamic_id, None, "failed", str(e))
                raise


async def comment_dynamic(dynamic_id: str, content: str, credential: Credential, max_retries: int = 3) -> bool:
    """评论动态"""
    for attempt in range(max_retries):
        try:
            await send_comment(
                text=content,
                oid=int(dynamic_id),
                type_=CommentResourceType.DYNAMIC,
                credential=credential
            )
            log_action("comment", dynamic_id, None, "success")
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                wait = random.uniform(2, 4)
                await asyncio.sleep(wait)
            else:
                log_action("comment", dynamic_id, None, "failed", str(e))
                raise


async def like_dynamic(dynamic_id: str, credential: Credential, max_retries: int = 3) -> bool:
    """点赞动态"""
    for attempt in range(max_retries):
        try:
            d = dynamic.Dynamic(dynamic_id=dynamic_id, credential=credential)
            await d.set_like()
            log_action("like", dynamic_id, None, "success")
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                wait = random.uniform(2, 4)
                await asyncio.sleep(wait)
            else:
                log_action("like", dynamic_id, None, "failed", str(e))
                raise


async def participate_forward_lottery(
    dynamic_id: str,
    uid: int,
    requirements: dict,
    credential: Credential,
    comment_content: str = "参与抽奖"
):
    """
    参与转发抽奖

    Args:
        dynamic_id: 动态 ID
        uid: UP 主 UID
        requirements: 需要执行的操作 {"follow": bool, "repost": bool, "comment": bool, "like": bool}
        credential: 登录凭证
        comment_content: 评论内容
    """
    results = {}

    # 1. 关注
    if requirements.get("follow"):
        try:
            print(f"正在关注 UP 主 {uid}...")
            await follow_user(uid, credential)
            print(f"关注完成")
            results["follow"] = True
            await asyncio.sleep(random.uniform(2, 4))
        except Exception as e:
            print(f"关注失败: {e}")
            results["follow"] = False

    # 2. 转发
    if requirements.get("repost"):
        try:
            print(f"正在转发动态 {dynamic_id}...")
            await repost_dynamic(dynamic_id, credential)
            print(f"转发完成")
            results["repost"] = True
            await asyncio.sleep(random.uniform(3, 5))
        except Exception as e:
            print(f"转发失败: {e}")
            results["repost"] = False

    # 3. 评论
    if requirements.get("comment"):
        try:
            print(f"正在评论动态 {dynamic_id}...")
            await comment_dynamic(dynamic_id, comment_content, credential)
            print(f"评论完成")
            results["comment"] = True
            await asyncio.sleep(random.uniform(2, 4))
        except Exception as e:
            print(f"评论失败: {e}")
            results["comment"] = False

    # 4. 点赞
    if requirements.get("like"):
        try:
            print(f"正在点赞动态 {dynamic_id}...")
            await like_dynamic(dynamic_id, credential)
            print(f"点赞完成")
            results["like"] = True
        except Exception as e:
            print(f"点赞失败: {e}")
            results["like"] = False

    return results


async def participate_interactive_lottery(dynamic_id: str, uid: int, credential: Credential):
    """
    参与互动抽奖（通过参与按钮一键完成关注+转发）
    """
    requirements = {"follow": True, "repost": True, "comment": False, "like": False}
    return await participate_forward_lottery(dynamic_id, uid, requirements, credential)


# 普通评论模板（非抽奖相关）
NORMAL_COMMENTS = [
    "好看！",
    "不错不错",
    "支持一下",
    "有意思",
    "厉害了",
    "哈哈",
    "学到了",
    "感谢分享",
    "太棒了",
    "666",
    "涨知识了",
    "好活",
    "顶",
    "赞",
]


async def delete_dynamic(dynamic_id: str, credential: Credential, max_retries: int = 3) -> bool:
    """删除动态，返回是否成功"""
    for attempt in range(max_retries):
        try:
            d = dynamic.Dynamic(dynamic_id=dynamic_id, credential=credential)
            await d.delete()
            log_action("delete", dynamic_id, None, "success")
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                wait = random.uniform(2, 4)
                await asyncio.sleep(wait)
            else:
                log_action("delete", dynamic_id, None, "failed", str(e))
                raise


async def random_interact_hot(dynamic_id: str, credential: Credential, actions: list = None):
    """
    随机转发热门动态（模拟正常用户行为）

    Args:
        dynamic_id: 动态 ID
        credential: 登录凭证
        actions: 可选的操作列表，默认 ["repost"]

    Returns:
        dict: 操作结果
    """
    if actions is None:
        actions = ["repost"]

    results = {}

    # 随机决定执行哪些操作
    selected_actions = random.sample(actions, min(random.randint(1, 2), len(actions)))

    if "like" in selected_actions:
        try:
            print(f"  点赞动态 {dynamic_id}...")
            await like_dynamic(dynamic_id, credential)
            results["like"] = True
            await asyncio.sleep(random.uniform(1, 3))
        except Exception as e:
            print(f"  点赞失败: {e}")
            results["like"] = False

    if "comment" in selected_actions:
        try:
            comment = random.choice(NORMAL_COMMENTS)
            print(f"  评论动态 {dynamic_id}: {comment}")
            await comment_dynamic(dynamic_id, comment, credential)
            results["comment"] = True
            await asyncio.sleep(random.uniform(1, 3))
        except Exception as e:
            print(f"  评论失败: {e}")
            results["comment"] = False

    if "repost" in selected_actions:
        try:
            print(f"  转发动态 {dynamic_id}...")
            await repost_dynamic(dynamic_id, credential)
            results["repost"] = True
        except Exception as e:
            print(f"  转发失败: {e}")
            results["repost"] = False

    return results