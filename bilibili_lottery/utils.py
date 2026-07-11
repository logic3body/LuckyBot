"""
通用工具函数
"""

import json
import pathlib
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

COMMENT_PRESETS = [
    "参与！",
    "冲冲冲！",
    "试试运气",
    "来啦来啦",
    "参与一下",
    "支持一下",
    "试试手气",
    "希望好运",
    "参与~",
    "来了来了",
]

LOGS_DIR = pathlib.Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

MAX_LOG_DAYS = 7


def get_today_log_file():
    """获取今天的日志文件路径"""
    today = datetime.now().strftime("%Y-%m-%d")
    return LOGS_DIR / f"{today}.log"


def clean_old_logs():
    """清理超过 7 天的日志文件"""
    cutoff = datetime.now() - timedelta(days=MAX_LOG_DAYS)
    for log_file in LOGS_DIR.glob("*.log"):
        if log_file.is_file():
            mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
            if mtime < cutoff:
                log_file.unlink()


def log_action(action: str, dyn_id: str, uid: int = None, result: str = "success", reason: str = None, extra: dict = None):
    """
    记录操作日志

    Args:
        action: 操作类型 (follow/repost/comment/like)
        dyn_id: 动态 ID
        uid: UP 主 UID
        result: 结果 (success/failed)
        reason: 失败原因
        extra: 额外信息
    """
    log_entry = {
        "time": datetime.now().isoformat(),
        "action": action,
        "dyn_id": str(dyn_id),
        "result": result,
    }
    if uid:
        log_entry["uid"] = str(uid)
    if reason:
        log_entry["reason"] = reason
    if extra:
        log_entry["extra"] = extra

    log_file = get_today_log_file()
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


def load_crawled_ids(path: pathlib.Path = pathlib.Path("crawled_ids.json"), max_count: int = 100) -> list:
    """加载已爬取动态 ID 列表"""
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("ids", [])[-max_count:]
    except (json.JSONDecodeError, IOError):
        return []


def save_crawled_ids(ids: list, path: pathlib.Path = pathlib.Path("crawled_ids.json"), max_count: int = 100):
    """保存已爬取动态 ID 列表（保留最近 max_count 条）"""
    ids = ids[-max_count:]
    data = {"ids": ids}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_participated(path: pathlib.Path = pathlib.Path("participated.json")) -> set:
    """加载已参与抽奖的动态 ID 集合"""
    if not path.exists():
        return set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(data.get("ids", []))
    except (json.JSONDecodeError, IOError):
        return set()


def save_participated(ids: set, path: pathlib.Path = pathlib.Path("participated.json")):
    """保存已参与抽奖的动态 ID 集合"""
    data = {"ids": list(ids)}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_participated(dyn_id: str, path: pathlib.Path = None, memory: set = None):
    """添加已参与记录

    同时可更新内存中的集合，避免同一个进程内重复参与。

    Args:
        dyn_id: 动态 ID
        path: participated.json 路径，默认 None 为项目根目录
        memory: 内存中的已参与集合（可选），传入后同步更新
    """
    if path is None:
        path = pathlib.Path("participated.json")
    ids = load_participated(path)
    ids.add(dyn_id)
    save_participated(ids, path)
    if memory is not None:
        memory.add(dyn_id)


def load_notified_winnings(path: pathlib.Path = pathlib.Path("notified_winnings.json")) -> set:
    """加载已推送的中奖通知 ID 集合"""
    if not path.exists():
        return set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(data.get("ids", []))
    except (json.JSONDecodeError, IOError):
        return set()


def save_notified_winnings(ids: set, path: pathlib.Path = pathlib.Path("notified_winnings.json")):
    """保存已推送的中奖通知 ID 集合"""
    data = {"ids": list(ids)}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_notified_winning(winning_id: str, path: pathlib.Path = pathlib.Path("notified_winnings.json")):
    """添加已推送的中奖记录"""
    ids = load_notified_winnings(path)
    ids.add(winning_id)
    save_notified_winnings(ids, path)


def log_winning(notification: dict):
    """
    记录可能的中奖通知

    Args:
        notification: 包含 source, content, url, time, keyword 的字典
    """
    log_entry = {
        "time": notification.get("time", datetime.now().isoformat()),
        "action": "winning_check",
        "source": notification.get("source", ""),
        "content": notification.get("content", ""),
        "url": notification.get("url", ""),
        "keyword": notification.get("keyword", ""),
    }

    log_file = get_today_log_file()
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


# ─── credential 持久化与自动刷新 ─────────────────────────────

CREDENTIAL_FILE = pathlib.Path("credential.json")


def load_credential() -> dict:
    """加载凭证，优先 credential.json，回退到 config.py"""
    if CREDENTIAL_FILE.exists():
        try:
            with open(CREDENTIAL_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    import config as _config
    return dict(_config.CREDENTIAL)


def save_credential(cred_data: dict):
    """保存凭证到 credential.json"""
    with open(CREDENTIAL_FILE, "w", encoding="utf-8") as f:
        json.dump(cred_data, f, indent=2, ensure_ascii=False)


async def ensure_credential(cred=None):
    """创建并确保 credential 有效，自动刷新并保存

    Args:
        cred: 可传入已有 Credential，否则从文件/config 加载

    Returns:
        有效的 Credential（已原地刷新）
    """
    from bilibili_api import Credential

    if cred is None:
        data = load_credential()
        cred = Credential(**data)

    if await cred.check_valid():
        return cred

    can_refresh = bool(cred.ac_time_value)
    if can_refresh:
        try:
            need_refresh = await cred.check_refresh()
        except Exception:
            need_refresh = True
    else:
        need_refresh = False

    if not need_refresh and not can_refresh:
        print("⚠ Cookie 已失效且缺少 ac_time_value，无法自动刷新")
        print("   请运行 python login_qrcode.py 重新登录")
        return cred

    if need_refresh:
        try:
            print("Cookie 即将过期，正在自动刷新...")
            await cred.refresh()
            save_credential({
                "sessdata": cred.sessdata,
                "bili_jct": cred.bili_jct,
                "buvid3": cred.buvid3,
                "buvid4": getattr(cred, "buvid4", "") or "",
                "dedeuserid": getattr(cred, "dedeuserid", "") or "",
                "ac_time_value": cred.ac_time_value,
            })
            print("✅ Cookie 刷新成功！")
        except Exception as e:
            print(f"❌ Cookie 刷新失败: {e}")
            print("   请运行 python login_qrcode.py 重新登录")

    return cred


def serverchan_push(sckey: str, title: str, content: str) -> bool:
    """
    通过 Server酱 推送消息

    Args:
        sckey: Server酱 SCKEY
        title: 消息标题
        content: 消息内容

    Returns:
        bool: 是否推送成功
    """
    if not sckey:
        return False

    try:
        # 新版 Server酱 Turbo: key 以 SCT 开头
        if sckey.startswith("SCT"):
            url = f"https://sctapi.ftqq.com/{sckey}.send"
            data = urllib.parse.urlencode({
                "title": title,
                "desp": content,
            }).encode("utf-8")
        else:
            # 旧版 Server酱
            url = f"https://sc.ftqq.com/{sckey}.send"
            data = urllib.parse.urlencode({
                "text": title,
                "desp": content,
            }).encode("utf-8")

        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result.get("errno", 0) == 0 or result.get("code", 0) == 0

    except Exception as e:
        print(f"Server酱推送失败: {e}")
        return False