"""
CLI 入口
"""

import asyncio
import importlib
import json
import random
import sys

from bilibili_api import Credential

from bilibili_lottery import (
    fetch_up_dynamics,
    fetch_follow_lotteries,
    get_dynamic_content,
    get_dynamic_author_uid,
    get_hot_dynamics,
    fetch_own_dynamics,
    delete_dynamic,
    parse_forward_requirements,
    participate_forward_lottery,
    participate_interactive_lottery,
    check_lottery_winning,
    print_winning_notifications,
    COMMENT_PRESETS,
    extract_dynamic_id,
    check_cookie_valid,
    random_interact_hot,
)
from bilibili_lottery.fetcher import LATEST_FILE, CLASSIFIED_DIR
from bilibili_lottery.classifier import classify_dynamics, save_classified_prizes
from bilibili_lottery.utils import (
    load_participated,
    add_participated,
    clean_old_logs,
    log_action,
    log_winning,
    serverchan_push,
)


async def cmd_fetch(uid: int):
    """获取动态并分类"""
    try:
        user_config = importlib.import_module("config")
    except ModuleNotFoundError:
        print("请先创建 config.py 文件")
        return

    cred = Credential(**user_config.CREDENTIAL)
    max_age = getattr(user_config, "MAX_DYNAMIC_AGE_HOURS", 168)

    print(f"正在获取 UID {uid} 的动态...")
    dynamics = await fetch_up_dynamics(uid, cred, limit=20, max_age_hours=max_age)

    if not dynamics:
        print("没有新的动态")
        return

    # 分类
    classified = classify_dynamics(dynamics)

    # 保存 latest.json
    with open(LATEST_FILE, "w", encoding="utf-8") as f:
        json.dump(dynamics, f, ensure_ascii=False, indent=2)

    # 保存分类文件
    for cat_name, items in classified.items():
        if items:
            file_path = CLASSIFIED_DIR / f"{cat_name}.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)

    print(f"获取完成，共发现:")
    for cat_name, items in classified.items():
        if items:
            print(f"  {cat_name}: {len(items)} 个")

    return classified


async def cmd_run():
    """执行完整工作流"""
    try:
        user_config = importlib.import_module("config")
    except ModuleNotFoundError:
        print("请先创建 config.py 文件")
        return

    # 清理旧日志
    clean_old_logs()

    cred = Credential(**user_config.CREDENTIAL)
    uid = user_config.TARGET_UID
    max_age = getattr(user_config, "MAX_DYNAMIC_AGE_HOURS", 168)

    # 加载已参与记录（用于去重）
    participated = load_participated()

    # 获取动态，用 participated 做去重（而非 crawled_ids）
    print(f"正在获取 UID {uid} 的动态...")
    dynamics = await fetch_up_dynamics(uid, cred, limit=20,
                                       max_age_hours=max_age,
                                       skip_ids=participated)

    if not dynamics:
        print("没有新的动态，退出")
        log_action("run", "", uid, "skipped", "no_new_dynamics")
        return

    print(f"获取到 {len(dynamics)} 条动态")

    # 保存 latest.json
    with open(LATEST_FILE, "w", encoding="utf-8") as f:
        json.dump(dynamics, f, ensure_ascii=False, indent=2)

    # 全量分类（供 cmd_forward / cmd_interact 使用）
    full_classified = classify_dynamics(dynamics)
    for cat_name, items in full_classified.items():
        if items:
            file_path = CLASSIFIED_DIR / f"{cat_name.replace('抽奖', '')}.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)

    # 只取最新 N 条动态参与抽奖
    max_process = getattr(user_config, "MAX_DYNAMICS_TO_PROCESS", 2)
    dynamics_to_process = dynamics[:max_process]
    classified = classify_dynamics(dynamics_to_process)

    print(f"分类结果: 转发抽奖 {len(classified['forward'])} 个, 互动抽奖 {len(classified['interact'])} 个")
    print(f"（仅处理最新 {len(dynamics_to_process)} 条动态中的抽奖）")

    # 处理转发抽奖
    for item in classified["forward"]:
        url = item.get("url", "")
        dyn_id = extract_dynamic_id(url)

        if not dyn_id:
            print(f"无法提取动态 ID: {url}")
            continue

        if dyn_id in participated:
            print(f"动态 {dyn_id} 已参与过，跳过")
            continue

        print(f"\n=== 处理转发抽奖: {item['name'][:30]}... ===")
        print(f"URL: {url}")
        print(f"动态 ID: {dyn_id}")

        try:
            # 获取动态内容和作者 UID
            content = await get_dynamic_content(dyn_id, cred)
            author_uid = await get_dynamic_author_uid(dyn_id, cred)
            print(f"动态内容: {content[:50]}...")
            print(f"作者 UID: {author_uid}")

            requirements = parse_forward_requirements(content)
            print(f"解析要求: {requirements}")

            random_comment = random.choice(COMMENT_PRESETS)
            result = await participate_forward_lottery(
                dyn_id, author_uid, requirements, cred,
                comment_content=random_comment
            )
            print(f"结果: {result}")

            # 无论是否需要操作，都标记为已处理（避免重复处理无需操作的项）
            add_participated(dyn_id)
            print(f"已添加参与记录: {dyn_id}")

        except Exception as e:
            print(f"处理失败: {e}")
            log_action("process_forward", dyn_id, 0, "failed", str(e))
            add_participated(dyn_id)
            print(f"已标记为已处理（失败）: {dyn_id}")

        # 间隔
        await asyncio.sleep(random.uniform(5, 10))

    # 处理互动抽奖
    for item in classified["interact"]:
        url = item.get("url", "")
        dyn_id = extract_dynamic_id(url)

        if not dyn_id:
            print(f"无法提取动态 ID: {url}")
            continue

        if dyn_id in participated:
            print(f"动态 {dyn_id} 已参与过，跳过")
            continue

        print(f"\n=== 处理互动抽奖: {item['name'][:30]}... ===")
        print(f"URL: {url}")
        print(f"动态 ID: {dyn_id}")

        try:
            # 获取作者 UID
            author_uid = await get_dynamic_author_uid(dyn_id, cred)
            print(f"作者 UID: {author_uid}")

            result = await participate_interactive_lottery(dyn_id, author_uid, cred)
            print(f"结果: {result}")

            # 无论是否需要操作，都标记为已处理
            add_participated(dyn_id)
            print(f"已添加参与记录: {dyn_id}")

        except Exception as e:
            print(f"处理失败: {e}")
            log_action("process_interact", dyn_id, 0, "failed", str(e))
            add_participated(dyn_id)
            print(f"已标记为已处理（失败）: {dyn_id}")

        # 间隔
        await asyncio.sleep(random.uniform(5, 10))

    print("\n工作流执行完成")


async def cmd_forward():
    """处理转发抽奖（独立运行）"""
    try:
        user_config = importlib.import_module("config")
    except ModuleNotFoundError:
        print("请先创建 config.py 文件")
        return

    cred = Credential(**user_config.CREDENTIAL)
    uid = user_config.TARGET_UID

    forward_file = CLASSIFIED_DIR / "forward.json"
    if not forward_file.exists():
        print("请先运行: python fetch.py run")
        return

    with open(forward_file, "r", encoding="utf-8") as f:
        forward_items = json.load(f)

    print(f"找到 {len(forward_items)} 个转发抽奖")

    participated = load_participated()

    for i, item in enumerate(forward_items, 1):
        url = item.get("url", "")
        dyn_id = extract_dynamic_id(url) or item.get("dyn_id", "")

        if not dyn_id or dyn_id in participated:
            continue

        print(f"\n=== [转发抽奖] 处理 {i}/{len(forward_items)}: {item['name'][:30]}... ===")

        try:
            content = await get_dynamic_content(dyn_id, cred)
            author_uid = await get_dynamic_author_uid(dyn_id, cred)
            requirements = parse_forward_requirements(content)

            random_comment = random.choice(COMMENT_PRESETS)
            result = await participate_forward_lottery(
                dyn_id, author_uid, requirements, cred,
                comment_content=random_comment
            )
            print(f"结果: {result}")

            # 无论是否需要操作，都标记为已处理
            add_participated(dyn_id)

        except Exception as e:
            print(f"失败: {e}")
            # 动态已删除/不可见等情况也标记为已处理，避免重复尝试
            add_participated(dyn_id)

        await asyncio.sleep(random.uniform(5, 10))


async def cmd_interact():
    """处理互动抽奖（独立运行）"""
    try:
        user_config = importlib.import_module("config")
    except ModuleNotFoundError:
        print("请先创建 config.py 文件")
        return

    cred = Credential(**user_config.CREDENTIAL)
    uid = user_config.TARGET_UID

    interact_file = CLASSIFIED_DIR / "interact.json"
    if not interact_file.exists():
        print("请先运行: python fetch.py run")
        return

    with open(interact_file, "r", encoding="utf-8") as f:
        interact_items = json.load(f)

    print(f"找到 {len(interact_items)} 个互动抽奖")

    participated = load_participated()

    for i, item in enumerate(interact_items, 1):
        url = item.get("url", "")
        dyn_id = extract_dynamic_id(url) or item.get("dyn_id", "")

        if not dyn_id or dyn_id in participated:
            continue

        print(f"\n=== [互动抽奖] 处理 {i}/{len(interact_items)}: {item['name'][:30]}... ===")

        try:
            author_uid = await get_dynamic_author_uid(dyn_id, cred)
            print(f"作者 UID: {author_uid}")

            result = await participate_interactive_lottery(dyn_id, author_uid, cred)
            print(f"结果: {result}")

            # 无论是否需要操作，都标记为已处理
            add_participated(dyn_id)

        except Exception as e:
            print(f"失败: {e}")
            add_participated(dyn_id)

        await asyncio.sleep(random.uniform(5, 10))


async def cmd_check_lottery():
    """检测可能的中奖通知"""
    try:
        user_config = importlib.import_module("config")
    except ModuleNotFoundError:
        print("请先创建 config.py 文件")
        return

    cred = Credential(**user_config.CREDENTIAL)
    sckey = getattr(user_config, 'SERVERCHAN_SCKEY', '') or ''

    print("正在检测通知中可能的中奖信息...")
    results = await check_lottery_winning(cred)

    # 打印结果
    print_winning_notifications(results)

    # 记录到日志并推送
    for notification in results:
        log_winning(notification)

    # Server酱推送
    if results and sckey:
        title = f"检测到 {len(results)} 条可能的中奖通知"
        content_lines = [f"检测到 {len(results)} 条可能的中奖通知:\n"]
        for i, item in enumerate(results, 1):
            content_lines.append(f"{i}. 来源: {item['source']}")
            content_lines.append(f"   内容: {item['content'][:50]}...")
            content_lines.append(f"   链接: {item['url']}")
            content_lines.append(f"   时间: {item['time']}")
            content_lines.append("")

        content = "\n".join(content_lines)
        print(f"\n正在推送 Server酱...")
        success = serverchan_push(sckey, title, content)
        if success:
            print("推送成功!")
        else:
            print("推送失败，请检查 SCKEY")


async def cmd_check_cookie():
    """检查 Cookie 是否有效，失效时推送通知"""
    try:
        user_config = importlib.import_module("config")
    except ModuleNotFoundError:
        print("请先创建 config.py 文件")
        return

    cred = Credential(**user_config.CREDENTIAL)
    sckey = getattr(user_config, 'SERVERCHAN_SCKEY', '') or ''

    print("正在检查 Cookie 有效性...")
    is_valid = await check_cookie_valid(cred)

    if is_valid:
        print("Cookie 有效")
        return

    print("Cookie 已失效!")

    # Server酱推送
    if sckey:
        title = "B站 Cookie 已失效"
        content = "请尽快更新 config.py 中的 CREDENTIAL 配置\n\n包括: sessdata, bili_jct, buvid3\n\n获取方式: 登录 bilibili.com → F12 → Application → Cookies"

        print("正在推送 Server酱...")
        success = serverchan_push(sckey, title, content)
        if success:
            print("推送成功!")
        else:
            print("推送失败，请检查 SCKEY")
    else:
        print("未配置 SERVERCHAN_SCKEY，跳过推送")


async def cmd_random_interact(count: int = 3):
    """随机互动热门动态（模拟正常用户行为）"""
    try:
        user_config = importlib.import_module("config")
    except ModuleNotFoundError:
        print("请先创建 config.py 文件")
        return

    cred = Credential(**user_config.CREDENTIAL)

    print(f"正在获取热门动态...")
    hot_items = await get_hot_dynamics(cred)

    if not hot_items:
        print("未获取到热门动态")
        return

    # 随机选择指定数量的动态
    selected = random.sample(hot_items, min(count, len(hot_items)))
    print(f"将随机转发 {len(selected)} 条热门动态\n")

    for i, item in enumerate(selected, 1):
        # 提取动态 ID
        dyn_id = item.get("id_str", "") or item.get("id", "")
        if not dyn_id:
            continue

        # 提取作者信息
        modules = item.get("modules", {})
        author = modules.get("module_author", {})
        author_name = author.get("name", "未知")

        print(f"[{i}/{len(selected)}] 动态 {dyn_id} (作者: {author_name})")

        try:
            result = await random_interact_hot(dyn_id, cred)
            print(f"  结果: {result}")
        except Exception as e:
            print(f"  失败: {e}")

        # 随机间隔，模拟真人
        await asyncio.sleep(random.uniform(10, 30))

    print(f"\n随机转发完成")


async def cmd_follow():
    """处理关注动态流中的抽奖"""
    try:
        user_config = importlib.import_module("config")
    except ModuleNotFoundError:
        print("请先创建 config.py 文件")
        return

    cred = Credential(**user_config.CREDENTIAL)

    # 获取自己的 UID
    from bilibili_api import user as user_module
    self_info = await user_module.get_self_info(cred)
    self_uid = self_info["mid"]

    # 排除自己和抽奖汇总号
    exclude_uids = {self_uid, user_config.TARGET_UID}

    participated = load_participated()

    print("正在扫描关注动态流...")
    candidates = await fetch_follow_lotteries(
        cred, limit=200, skip_ids=participated,
        exclude_uids=exclude_uids,
    )

    if not candidates:
        print("没有找到抽奖动态")
        return

    print(f"将参与 {len(candidates)} 条抽奖动态\n")

    for i, c in enumerate(candidates, 1):
        dyn_id = c["dyn_id"]

        print(f"[{i}/{len(candidates)}] {c['author_name']}: ", end="")
        print(f"{c['content'][:80]}...")

        try:
            requirements = parse_forward_requirements(c["content"])
            print(f"  解析要求: {requirements}")

            random_comment = random.choice(COMMENT_PRESETS)
            result = await participate_forward_lottery(
                dyn_id, c["author_uid"], requirements, cred,
                comment_content=random_comment
            )
            print(f"  结果: {result}")

            add_participated(dyn_id)

        except Exception as e:
            print(f"  处理失败: {e}")
            log_action("process_follow", dyn_id, c["author_uid"], "failed", str(e))
            add_participated(dyn_id)

        await asyncio.sleep(random.uniform(5, 10))

    print(f"\n关注动态流处理完成")


async def cmd_clean(days: int = 30, confirm: bool = False):
    """批量清理旧动态"""
    from datetime import datetime
    from bilibili_api import user as user_module

    try:
        user_config = importlib.import_module("config")
    except ModuleNotFoundError:
        print("请先创建 config.py 文件")
        return

    cred = Credential(**user_config.CREDENTIAL)

    # 获取自己的 UID（而非 TARGET_UID）
    self_info = await user_module.get_self_info(cred)
    uid = self_info["mid"]
    nickname = self_info.get("name", "")
    print(f"当前账号: {nickname} (UID: {uid})")

    print(f"正在获取 {days} 天前的旧动态...")
    old_dynamics = await fetch_own_dynamics(uid, cred, days=days)

    if not old_dynamics:
        print(f"没有找到 {days} 天前的动态")
        return

    # 按时间排序（旧的在前）
    old_dynamics.sort(key=lambda x: x["timestamp"])

    print(f"\n找到 {len(old_dynamics)} 条 {days} 天前的动态:\n")
    print(f"{'序号':<6}{'发布时间':<22}{'动态 ID':<20}{'内容摘要'}")
    print("-" * 80)
    for i, d in enumerate(old_dynamics, 1):
        pub_time = datetime.fromtimestamp(d["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
        summary = d["content_summary"][:30] if d["content_summary"] else "(无文字内容)"
        print(f"{i:<6}{pub_time:<22}{d['dynamic_id']:<20}{summary}")

    # 确认删除
    if not confirm:
        print(f"\n共 {len(old_dynamics)} 条动态将被删除。")
        answer = input("确认删除？(y/N): ").strip().lower()
        if answer != "y":
            print("已取消")
            return

    # 执行删除
    print(f"\n开始删除...")
    success_count = 0
    fail_count = 0

    for i, d in enumerate(old_dynamics, 1):
        dyn_id = d["dynamic_id"]
        print(f"[{i}/{len(old_dynamics)}] 删除动态 {dyn_id}...", end=" ")
        try:
            result = await delete_dynamic(dyn_id, cred)
            if result:
                print("成功")
                success_count += 1
            else:
                print("失败")
                fail_count += 1
        except Exception as e:
            print(f"失败: {e}")
            fail_count += 1

        # 随机延迟，避免触发风控
        await asyncio.sleep(random.uniform(0.3, 0.8))

    print(f"\n清理完成: 成功 {success_count}, 失败 {fail_count}, 共 {len(old_dynamics)} 条")


def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  python fetch.py run              - 执行完整工作流")
        print("  python fetch.py fetch <uid>      - 仅获取动态")
        print("  python fetch.py forward          - 处理转发抽奖")
        print("  python fetch.py interact         - 处理互动抽奖")
        print("  python fetch.py check-lottery    - 检测是否中奖")
        print("  python fetch.py check-cookie     - 检查 Cookie 是否有效")
        print("  python fetch.py follow          - 参与关注动态流中的抽奖")
        print("  python fetch.py random [N]       - 随机转发 N 条热门动态（默认 3）")
        print("  python fetch.py clean [--days N] [--confirm] - 清理 N 天前的旧动态（默认 30）")
        return

    mode = sys.argv[1]

    if mode == "run":
        asyncio.run(cmd_run())
    elif mode == "fetch":
        if len(sys.argv) < 3:
            print("请提供 UID: python fetch.py fetch <uid>")
            return
        uid = int(sys.argv[2])
        asyncio.run(cmd_fetch(uid))
    elif mode == "forward":
        asyncio.run(cmd_forward())
    elif mode == "interact":
        asyncio.run(cmd_interact())
    elif mode == "check-lottery":
        asyncio.run(cmd_check_lottery())
    elif mode == "check-cookie":
        asyncio.run(cmd_check_cookie())
    elif mode == "follow":
        asyncio.run(cmd_follow())
    elif mode == "random":
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 3
        asyncio.run(cmd_random_interact(count))
    elif mode == "clean":
        days = 30
        confirm = False
        args = sys.argv[2:]
        i = 0
        while i < len(args):
            if args[i] == "--days" and i + 1 < len(args):
                days = int(args[i + 1])
                i += 2
            elif args[i] == "--confirm":
                confirm = True
                i += 1
            else:
                i += 1
        asyncio.run(cmd_clean(days=days, confirm=confirm))
    else:
        print(f"未知模式: {mode}")


if __name__ == "__main__":
    main()