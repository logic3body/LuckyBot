"""
bilibili-lottery - 哔哩哔哩抽奖参与工具
"""

from .fetcher import fetch_up_dynamics, get_dynamic_content, get_dynamic_author_uid, get_hot_dynamics
from .classifier import parse_classified_prizes, save_classified_prizes, classify_dynamics
from .parser import extract_dynamic_id, parse_forward_requirements
from .participant import (
    follow_user,
    repost_dynamic,
    comment_dynamic,
    like_dynamic,
    participate_forward_lottery,
    participate_interactive_lottery,
    random_interact_hot,
)
from .notifier import check_lottery_winning, print_winning_notifications, LOTTERY_KEYWORDS, check_cookie_valid
from .utils import COMMENT_PRESETS

__all__ = [
    "fetch_up_dynamics",
    "get_dynamic_content",
    "get_dynamic_author_uid",
    "get_hot_dynamics",
    "parse_classified_prizes",
    "save_classified_prizes",
    "classify_dynamics",
    "extract_dynamic_id",
    "parse_forward_requirements",
    "follow_user",
    "repost_dynamic",
    "comment_dynamic",
    "like_dynamic",
    "participate_forward_lottery",
    "participate_interactive_lottery",
    "random_interact_hot",
    "check_lottery_winning",
    "print_winning_notifications",
    "LOTTERY_KEYWORDS",
    "check_cookie_valid",
    "COMMENT_PRESETS",
]