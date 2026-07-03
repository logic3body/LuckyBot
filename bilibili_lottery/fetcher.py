"""
动态获取模块
"""

import asyncio
import json
import pathlib
import random
import time

from bilibili_api import Credential, user, dynamic
from bilibili_api.utils.utils import get_api
from bilibili_api.utils.network import Api

from .utils import load_crawled_ids, save_crawled_ids

DYNAMICS_DIR = pathlib.Path("dynamics")
DYNAMICS_DIR.mkdir(exist_ok=True)
CLASSIFIED_DIR = DYNAMICS_DIR / "classified"
CLASSIFIED_DIR.mkdir(exist_ok=True)
LATEST_FILE = DYNAMICS_DIR / "latest.json"

# 加载动态 API 定义
DYNAMIC_API = get_api("dynamic")


def set_proxy(proxy: str = ""):
    """设置代理（预留接口）"""
    pass


async def get_hot_dynamics(credential: Credential = None, page: int = 1, retry: int = 3) -> list:
    """
    获取热门动态列表

    Args:
        credential: 登录凭证（可选）
        page: 页码，默认 1
        retry: 重试次数

    Returns:
        list: 动态列表
    """
    for attempt in range(retry):
        try:
            api = DYNAMIC_API["info"]["hot_dynamics"]
            params = {
                "page": page,
                "features": "itemOpusStyle",
            }
            result = await Api(**api, credential=credential).update_params(**params).result

            items = result.get("items", [])
            return items
        except Exception as e:
            if attempt < retry - 1:
                wait_time = (attempt + 1) * 3 + random.uniform(1, 2)
                print(f"获取热门动态失败，{wait_time:.1f}秒后重试... ({attempt + 1}/{retry})")
                await asyncio.sleep(wait_time)
            else:
                raise


def get_publish_timestamp(opus_info: dict) -> int:
    """从 opus_info 中提取动态的发布时间戳"""
    modules = opus_info.get("item", {}).get("modules", {})

    if isinstance(modules, dict):
        return int(modules.get("module_author", {}).get("pub_ts", 0))

    if isinstance(modules, list):
        for mod in modules:
            if mod.get("module_type") == "MODULE_TYPE_AUTHOR":
                return int(mod.get("module_author", {}).get("pub_ts", 0))

    return 0


async def fetch_up_dynamics(uid: int, credential: Credential, limit: int = 20,
                            retry: int = 3, max_age_hours: int = 168,
                            skip_ids: set = None):
    """爬取指定 UP 主的最新动态，带重试和间隔，自动去重

    Args:
        uid: UP 主 UID
        credential: 登录凭证
        limit: 每次最多处理多少条
        retry: 重试次数
        max_age_hours: 动态最大时效（小时），超过此时间的跳过，默认 168（7 天）
        skip_ids: 要跳过的动态 ID 集合（如已参与记录），
                  传入后取代 crawled_ids 作为去重依据
    """
    # 加载已爬取记录（仅用作 session 缓存，不做硬去重）
    crawled_ids = load_crawled_ids()
    now = time.time()

    for attempt in range(retry):
        try:
            # 使用 get_dynamic_page_list 获取完整动态数据
            dynamics = await dynamic.get_dynamic_page_list(
                host_mid=uid,
                credential=credential
            )

            new_ids = []
            new_dynamics = []
            for d in dynamics[:limit]:
                try:
                    # 获取动态 ID
                    dyn_id = str(d.get_dynamic_id())
                    if not dyn_id:
                        continue

                    # 去重检查：优先用 skip_ids（已参与），否则用 crawled_ids
                    if skip_ids is not None:
                        if dyn_id in skip_ids:
                            continue
                    else:
                        if dyn_id in crawled_ids:
                            continue

                    # 已在本 session 中处理过，跳过（防重复 API 调用）
                    if dyn_id in new_ids:
                        continue

                    opus = d.turn_to_opus()
                    opus_info = await opus.get_info()

                    if not isinstance(opus_info, dict):
                        print(f"动态 {dyn_id} 返回非预期数据格式，跳过")
                        continue

                    # 按发布时间过滤过时动态
                    pub_ts = get_publish_timestamp(opus_info)
                    if pub_ts and (now - pub_ts) > max_age_hours * 3600:
                        print(f"动态 {dyn_id} 已超过 {max_age_hours} 小时，跳过")
                        continue

                    new_dynamics.append(opus_info)
                    new_ids.append(dyn_id)
                    await asyncio.sleep(random.uniform(1.0, 2.0))
                except Exception as e:
                    print(f"获取动态详情失败: {e}")
                    continue

            # 更新已爬取记录（仅作为 session 缓存，不影响下次运行的去重）
            if new_ids:
                crawled_ids.extend(new_ids)
                save_crawled_ids(crawled_ids)

            return new_dynamics

        except Exception as e:
            if attempt < retry - 1:
                wait_time = (attempt + 1) * 5 + random.uniform(1, 3)
                print(f"获取动态失败，{wait_time:.1f}秒后重试... ({attempt + 1}/{retry})")
                await asyncio.sleep(wait_time)
            else:
                raise


async def get_dynamic_content(dynamic_id: str, credential: Credential, retry: int = 3) -> str:
    """获取动态的文字内容（用于解析转发抽奖要求）"""
    for attempt in range(retry):
        try:
            d = dynamic.Dynamic(dynamic_id=dynamic_id, credential=credential)
            info = await d.get_info()

            if not isinstance(info, dict):
                raise ValueError(f"Unexpected info type: {type(info)}")

            if "item" in info:
                modules = info.get("item", {}).get("modules", {})
            else:
                modules = info.get("modules", {})

            texts = []

            if isinstance(modules, dict):
                mod_dyn = modules.get("module_dynamic", {})
                desc = mod_dyn.get("desc")
                if desc is not None:
                    rich_nodes = desc.get("rich_text_nodes", [])
                    for node in rich_nodes:
                        text = node.get("text", "")
                        texts.append(text)
                # 尝试从 major.opus 获取内容
                major = mod_dyn.get("major")
                if major and isinstance(major, dict) and "opus" in major:
                    summary = major["opus"].get("summary", {})
                    text = summary.get("text", "")
                    if text:
                        texts.append(text)
                return "".join(texts)

            if isinstance(modules, list):
                for mod in modules:
                    mod_type = mod.get("module_type")
                    if mod_type == "MODULE_TYPE_CONTENT":
                        content = mod.get("module_content", {})
                        paragraphs = content.get("paragraphs", [])
                        for para in paragraphs:
                            text_nodes = para.get("text", {}).get("nodes", [])
                            for node in text_nodes:
                                if node.get("type") == "TEXT_NODE_TYPE_WORD":
                                    words = node.get("word", {}).get("words", "")
                                    texts.append(words)
                return "".join(texts)

            return ""

        except Exception as e:
            if attempt < retry - 1:
                wait_time = (attempt + 1) * 3 + random.uniform(1, 2)
                print(f"获取动态内容失败，{wait_time:.1f}秒后重试... ({attempt + 1}/{retry})")
                await asyncio.sleep(wait_time)
            else:
                raise


# ── 关注动态流抽奖检测 ─────────────────────────────────────

LOTTERY_DETECT_KEYWORDS = [
    "抽奖", "抽送", "抽一位", "抽两位", "抽一位", "抽二位",
    "抽1位", "抽2位", "抽3位", "抽4位", "抽5位",
    "抽6位", "抽7位", "抽8位", "抽9位", "抽10位",
    "抽一名", "抽两名",
    "送.*位",   # 不用于精确匹配，这里只是文档说明
]


def extract_text_from_feed_item(item: dict) -> str:
    """从 get_dynamic_page_info 返回的 item dict 中提取文字内容

    文字可能在两个位置：
    1. desc.rich_text_nodes（纯文字动态）
    2. major.opus.summary.text（opus 格式动态）
    """
    modules = item.get("modules")
    if not isinstance(modules, dict):
        return ""
    dyn_mod = modules.get("module_dynamic")
    if not isinstance(dyn_mod, dict):
        return ""

    texts = []

    # 来源 1：desc.rich_text_nodes
    desc = dyn_mod.get("desc")
    if isinstance(desc, dict):
        nodes = desc.get("rich_text_nodes", [])
        for node in nodes:
            if isinstance(node, dict):
                t = node.get("text", "")
                if t:
                    texts.append(t)

    # 来源 2：major.opus.summary.text（MAJOR_TYPE_OPUS 格式）
    major = dyn_mod.get("major")
    if isinstance(major, dict) and major.get("type") == "MAJOR_TYPE_OPUS":
        opus = major.get("opus")
        if isinstance(opus, dict):
            summary = opus.get("summary")
            if isinstance(summary, dict):
                t = summary.get("text", "")
                if t:
                    texts.append(t)

    return "".join(texts)


def extract_author_from_feed_item(item: dict) -> tuple:
    """从 item dict 提取作者信息，返回 (name, mid)"""
    modules = item.get("modules")
    if not isinstance(modules, dict):
        return ("", 0)
    author = modules.get("module_author")
    if not isinstance(author, dict):
        return ("", 0)
    return (author.get("name", ""), author.get("mid", 0))


def is_lottery_text(text: str) -> bool:
    """判断文字是否包含抽奖相关关键词"""
    if not text:
        return False
    for kw in LOTTERY_DETECT_KEYWORDS:
        if kw in text:
            return True
    return False


async def fetch_follow_lotteries(credential: Credential, limit: int = 60,
                                 retry: int = 3, skip_ids: set = None) -> list:
    """获取关注动态流，筛选出抽奖动态

    使用 get_dynamic_page_info 不传 host_mid，获取当前用户的所有关注动态，
    直接从返回的 item dict 中提取文字和作者信息，无需额外 API 调用。

    Args:
        credential: 登录凭证
        limit: 最多检查多少条动态
        retry: 重试次数
        skip_ids: 要跳过的动态 ID 集合（如已参与记录）

    Returns:
        list[dict]: {dyn_id, author_uid, content, author_name}
    """
    if skip_ids is None:
        skip_ids = set()

    for attempt in range(retry):
        try:
            result = await dynamic.get_dynamic_page_info(credential=credential)
            items = result.get("items", [])
            print(f"  关注动态流共 {len(items)} 条")

            candidates = []
            for item in items[:limit]:
                dyn_id = str(item.get("id_str", ""))
                if not dyn_id or dyn_id in skip_ids:
                    continue

                text = extract_text_from_feed_item(item)
                if not is_lottery_text(text):
                    continue

                author_name, author_uid = extract_author_from_feed_item(item)
                if not author_uid:
                    continue

                candidates.append({
                    "dyn_id": dyn_id,
                    "author_uid": author_uid,
                    "content": text,
                    "author_name": author_name,
                })

            if candidates:
                print(f"  筛选出 {len(candidates)} 条抽奖动态")
            return candidates

        except Exception as e:
            if attempt < retry - 1:
                wait = (attempt + 1) * 5 + random.uniform(1, 3)
                print(f"获取关注动态失败，{wait:.1f}秒后重试... ({attempt + 1}/{retry})")
                await asyncio.sleep(wait)
            else:
                raise


async def fetch_own_dynamics(uid: int, credential: Credential, days: int = 30, retry: int = 3) -> list:
    """
    获取自己账号中指定天数前的旧动态

    Args:
        uid: 自己的 UID
        credential: 登录凭证
        days: 删除 N 天前的动态，默认 30
        retry: 重试次数

    Returns:
        list[dict]: 旧动态列表，每项包含 dynamic_id, timestamp, content_summary
    """
    from datetime import datetime, timedelta

    cutoff_ts = int((datetime.now() - timedelta(days=days)).timestamp())
    old_dynamics = []
    offset = None
    pn = 1

    for attempt in range(retry):
        try:
            while True:
                result = await dynamic.get_dynamic_page_info(
                    credential=credential,
                    host_mid=uid,
                    offset=offset,
                )

                items = result.get("items", [])
                if not items:
                    break

                # 动态按时间倒序排列，收集过期动态
                for item in items:
                    dyn_id_str = item.get("id_str", "")
                    if not dyn_id_str:
                        continue

                    modules = item.get("modules", {})
                    author = modules.get("module_author", {})
                    pub_ts = author.get("pub_ts", "0")
                    timestamp = int(pub_ts) if pub_ts else 0

                    if timestamp < cutoff_ts:
                        content_summary = ""
                        dyn_module = modules.get("module_dynamic", {})
                        desc = dyn_module.get("desc")
                        if desc and isinstance(desc, dict):
                            rich_nodes = desc.get("rich_text_nodes", [])
                            content_summary = "".join(
                                n.get("text", "") for n in rich_nodes
                            )[:50]

                        old_dynamics.append({
                            "dynamic_id": dyn_id_str,
                            "timestamp": timestamp,
                            "content_summary": content_summary,
                        })

                # 翻页
                has_more = result.get("has_more", False)
                if not has_more:
                    break
                new_offset = result.get("offset")
                if new_offset is None:
                    break
                offset = new_offset
                pn += 1
                if pn % 10 == 0 or old_dynamics:
                    print(f"  已扫描 {pn} 页, 找到 {len(old_dynamics)} 条旧动态...")

            return old_dynamics

        except Exception as e:
            if attempt < retry - 1:
                wait_time = (attempt + 1) * 5 + random.uniform(1, 3)
                print(f"获取动态失败，{wait_time:.1f}秒后重试... ({attempt + 1}/{retry})")
                await asyncio.sleep(wait_time)
            else:
                raise


async def get_dynamic_author_uid(dynamic_id: str, credential: Credential, retry: int = 3) -> int:
    """获取动态的作者 UID"""
    for attempt in range(retry):
        try:
            d = dynamic.Dynamic(dynamic_id=dynamic_id, credential=credential)
            info = await d.get_info()

            if not isinstance(info, dict):
                raise ValueError(f"Unexpected info type: {type(info)}")

            if "item" in info:
                modules = info.get("item", {}).get("modules", {})
            else:
                modules = info.get("modules", {})

            # modules 是 dict 格式
            if isinstance(modules, dict):
                author = modules.get("module_author", {})
                mid = author.get("mid", 0)
                if mid:
                    return mid
                return author.get("user", {}).get("mid", 0)

            # modules 是 list 格式
            if isinstance(modules, list):
                for mod in modules:
                    if "module_author" in mod:
                        author = mod["module_author"]
                        return author.get("mid", 0) or author.get("user", {}).get("mid", 0)

            return 0

        except Exception as e:
            if attempt < retry - 1:
                wait_time = (attempt + 1) * 3 + random.uniform(1, 2)
                print(f"获取动态作者失败，{wait_time:.1f}秒后重试... ({attempt + 1}/{retry})")
                await asyncio.sleep(wait_time)
            else:
                raise