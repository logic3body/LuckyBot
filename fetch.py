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
    get_dynamic_content,
    get_hot_dynamics,
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

    print(f"正在获取 UID {uid} 的动态...")
    dynamics = await fetch_up_dynamics(uid, cred, limit=20)

    if not dynamics:
        print("没有新的动态")
        return

    # 分类
    classified = classify_dynamics(dynamics)

    # 保存 latest.json
    import json
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

    # 获取动态
    print(f"正在获取 UID {uid} 的动态...")
    dynamics = await fetch_up_dynamics(uid, cred, limit=20)

    if not dynamics:
        print("没有新的动态，退出")
        log_action("run", "", uid, "skipped", "no_new_dynamics")
        return

    print(f"获取到 {len(dynamics)} 条动态")

    # 保存 latest.json
    with open(LATEST_FILE, "w", encoding="utf-8") as f:
        json.dump(dynamics, f, ensure_ascii=False, indent=2)

    # 分类
    classified = classify_dynamics(dynamics)
    print(f"分类结果: 转发抽奖 {len(classified['forward'])} 个, 互动抽奖 {len(classified['interact'])} 个")

    # 加载已参与记录
    participated = load_participated()

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
            content = await get_dynamic_content(dyn_id, cred)
            print(f"动态内容: {content[:50]}...")

            requirements = parse_forward_requirements(content)
            print(f"解析要求: {requirements}")

            random_comment = random.choice(COMMENT_PRESETS)
            result = await participate_forward_lottery(
                dyn_id, uid, requirements, cred,
                comment_content=random_comment
            )
            print(f"结果: {result}")

            if any(result.values()):
                add_participated(dyn_id)
                print(f"已添加参与记录: {dyn_id}")

        except Exception as e:
            print(f"处理失败: {e}")
            log_action("process_forward", dyn_id, uid, "failed", str(e))

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
            result = await participate_interactive_lottery(dyn_id, uid, cred)
            print(f"结果: {result}")

            if any(result.values()):
                add_participated(dyn_id)
                print(f"已添加参与记录: {dyn_id}")

        except Exception as e:
            print(f"处理失败: {e}")
            log_action("process_interact", dyn_id, uid, "failed", str(e))

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

    import json
    with open(forward_file, "r", encoding="utf-8") as f:
        forward_items = json.load(f)

    print(f"找到 {len(forward_items)} 个转发抽奖")

    participated = load_participated()

    for i, item in enumerate(forward_items, 1):
        dyn_id = item.get("dyn_id", "")

        if not dyn_id or dyn_id in participated:
            continue

        print(f"\n=== [转发抽奖] 处理 {i}/{len(forward_items)}: {item['name'][:30]}... ===")

        try:
            content = await get_dynamic_content(dyn_id, cred)
            requirements = parse_forward_requirements(content)

            random_comment = random.choice(COMMENT_PRESETS)
            result = await participate_forward_lottery(
                dyn_id, uid, requirements, cred,
                comment_content=random_comment
            )
            print(f"结果: {result}")

            if any(result.values()):
                add_participated(dyn_id)

        except Exception as e:
            print(f"失败: {e}")

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

    import json
    with open(interact_file, "r", encoding="utf-8") as f:
        interact_items = json.load(f)

    print(f"找到 {len(interact_items)} 个互动抽奖")

    participated = load_participated()

    for i, item in enumerate(interact_items, 1):
        dyn_id = item.get("dyn_id", "")

        if not dyn_id or dyn_id in participated:
            continue

        print(f"\n=== [互动抽奖] 处理 {i}/{len(interact_items)}: {item['name'][:30]}... ===")

        try:
            result = await participate_interactive_lottery(dyn_id, uid, cred)
            print(f"结果: {result}")

            if any(result.values()):
                add_participated(dyn_id)

        except Exception as e:
            print(f"失败: {e}")

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
    hot_items = await get_hot_dynamics()

    if not hot_items:
        print("未获取到热门动态")
        return

    # 随机选择指定数量的动态
    selected = random.sample(hot_items, min(count, len(hot_items)))
    print(f"将随机互动 {len(selected)} 条热门动态\n")

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

    print(f"\n随机互动完成")


def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  python fetch.py run            - 执行完整工作流")
        print("  python fetch.py fetch <uid>      - 仅获取动态")
        print("  python fetch.py forward          - 处理转发抽奖")
        print("  python fetch.py interact         - 处理互动抽奖")
        print("  python fetch.py check-lottery    - 检测是否中奖")
        print("  python fetch.py check-cookie     - 检查 Cookie 是否有效")
        print("  python fetch.py random [N]       - 随机互动 N 条热门动态（默认 3）")
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
    elif mode == "random":
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 3
        asyncio.run(cmd_random_interact(count))
    else:
        print(f"未知模式: {mode}")


if __name__ == "__main__":
    main()