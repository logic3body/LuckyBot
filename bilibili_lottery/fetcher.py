"""
动态获取模块
"""

import asyncio
import json
import pathlib
import random

from bilibili_api import Credential, user, dynamic

from .utils import load_crawled_ids, save_crawled_ids

DYNAMICS_DIR = pathlib.Path("dynamics")
DYNAMICS_DIR.mkdir(exist_ok=True)
CLASSIFIED_DIR = DYNAMICS_DIR / "classified"
CLASSIFIED_DIR.mkdir(exist_ok=True)
LATEST_FILE = DYNAMICS_DIR / "latest.json"


def set_proxy(proxy: str = ""):
    """设置代理（预留接口）"""
    pass


async def fetch_up_dynamics(uid: int, credential: Credential, limit: int = 20, retry: int = 3):
    """爬取指定 UP 主的最新动态，带重试和间隔，自动去重"""
    # 加载已爬取记录
    crawled_ids = load_crawled_ids()

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

                    # 去重检查
                    if dyn_id not in crawled_ids:
                        opus = d.turn_to_opus()
                        opus_info = await opus.get_info()

                        if opus_info is None:
                            print(f"动态 {dyn_id} 返回空数据，跳过")
                            continue

                        new_dynamics.append(opus_info)
                        new_ids.append(dyn_id)

                    await asyncio.sleep(random.uniform(1.0, 2.0))
                except Exception as e:
                    print(f"获取动态详情失败: {e}")
                    continue

            # 更新已爬取记录
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
                desc = mod_dyn.get("desc", {})
                rich_nodes = desc.get("rich_text_nodes", [])
                for node in rich_nodes:
                    text = node.get("text", "")
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