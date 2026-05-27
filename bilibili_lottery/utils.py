"""
通用工具函数
"""

import json
import pathlib
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


def load_crawled_ids(path: pathlib.Path = pathlib.Path("crawled_ids.json"), max_count: int = 10) -> list:
    """加载已爬取动态 ID 列表"""
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("ids", [])[-max_count:]
    except (json.JSONDecodeError, IOError):
        return []


def save_crawled_ids(ids: list, path: pathlib.Path = pathlib.Path("crawled_ids.json"), max_count: int = 10):
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


def add_participated(dyn_id: str, path: pathlib.Path = pathlib.Path("participated.json")):
    """添加已参与记录"""
    ids = load_participated(path)
    ids.add(dyn_id)
    save_participated(ids, path)