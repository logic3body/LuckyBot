"""
清理重复转发工具。

每个原始动态只保留最新的一条转发，删除多余的副本。
用于清理因 fix 前去重失效导致的重复转发。

用法:
    python cleanup_duplicates.py
"""

import asyncio, random, sys
from collections import Counter
from typing import Optional

from bilibili_api import Credential
from bilibili_api.dynamic import get_dynamic_page_info
import config

from bilibili_lottery import delete_dynamic
from bilibili_lottery.utils import load_credential as _load_cred

# 要清理的账号 UID（局中的旁观者）
OWN_UID = 3546871643506991


async def fetch_own_dynamics(cred: Credential):
    """拉取自己的所有动态"""
    all_items = []
    offset = None
    page = 1

    while True:
        result = await get_dynamic_page_info(
            credential=cred, host_mid=OWN_UID, offset=offset,
        )
        items = result.get('items', [])
        if not items:
            break

        for item in items:
            dyn_id = item.get('id_str', '')
            orig = item.get('orig')
            orig_id = ''
            if isinstance(orig, dict):
                orig_id = orig.get('id_str', orig.get('id', ''))
                if not orig_id:
                    orig_basic = orig.get('basic', {})
                    orig_id = orig_basic.get('rid_str', '')
            if orig_id:
                all_items.append({
                    'dyn_id': dyn_id,
                    'orig_id': str(orig_id),
                })

        if not result.get('has_more'):
            break
        offset = result.get('offset')
        page += 1

    return all_items


async def main():
    cred_data = _load_cred()
    cred = Credential(**cred_data)

    print("拉取自身动态列表...")
    items = await fetch_own_dynamics(cred)
    total = len(items)
    print(f"共 {total} 条转发动态\n")

    # 按 orig_id 分组
    orig_groups = {}
    for item in items:
        orig_groups.setdefault(item['orig_id'], []).append(item)

    # 找重复
    duplicates = {k: v for k, v in orig_groups.items() if len(v) > 1}
    if not duplicates:
        print("没有重复转发，无需清理。")
        return

    print(f"发现 {len(duplicates)} 个有重复转发的原始动态\n")

    # 构造删除列表：每组保留最新一条（dyn_id 最大），删除其余
    to_delete = []
    for orig_id, reposts in sorted(duplicates.items(), key=lambda x: -len(x[1])):
        sorted_reposts = sorted(reposts, key=lambda x: x['dyn_id'])
        keep = sorted_reposts[-1]
        remove = sorted_reposts[:-1]
        print(f"  原始 {orig_id}: {len(reposts)} 次 → 保留 {keep['dyn_id']}, 删 {len(remove)} 条")
        for r in remove:
            to_delete.append((orig_id, r['dyn_id']))

    print(f"\n共需删除 {len(to_delete)} 条动态")
    print("按 Enter 开始删除，或 Ctrl+C 取消...")
    try:
        input()
    except EOFError:
        pass

    # 分批执行
    success = fail = 0
    BATCH = 20
    for i in range(0, len(to_delete), BATCH):
        batch = to_delete[i:i + BATCH]
        batch_num = i // BATCH + 1
        total_batches = (len(to_delete) + BATCH - 1) // BATCH
        print(f"\n--- 批次 {batch_num}/{total_batches} ({len(batch)} 条) ---")

        for orig_id, dyn_id in batch:
            try:
                if await delete_dynamic(dyn_id, cred):
                    success += 1
                    print(f"  ✓ {dyn_id}")
                else:
                    fail += 1
                    print(f"  ✗ {dyn_id}")
            except Exception as e:
                fail += 1
                print(f"  ✗ {dyn_id}: {e}")
            await asyncio.sleep(random.uniform(1.0, 2.5))

        if i + BATCH < len(to_delete):
            print("  等待 10s...")
            await asyncio.sleep(10)

    print(f"\n===== 完成: 成功 {success}, 失败 {fail} =====")


if __name__ == '__main__':
    asyncio.run(main())
