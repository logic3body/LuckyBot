# bilibili-lottery

哔哩哔哩抽奖参与工具，自动获取 UP 主（如"互动抽奖娘"）的抽奖合集动态，分类提取转发抽奖、互动抽奖等链接，自动参与。

## 功能

- 自动获取 UP 主动态（支持去重）
- 分类提取：转发抽奖、充电抽奖、预约抽奖、互动抽奖
- 智能解析抽奖要求（关注/转发/评论/点赞）
- 失败重试机制（每操作 3 次重试）
- 完整操作日志（JSON Lines 格式）
- 中奖检测与 Server 酱推送
- Cookie 有效性检查
- 批量清理旧动态
- 随机互动热门动态（模拟正常用户行为）
- 定时任务支持（青龙面板等）

## 安装

```bash
# 克隆后安装依赖
pip install -r requirements.txt

# 或使用 uv
uv pip install -r requirements.txt
```

## 配置

复制 `config.py.example` 为 `config.py` 并填写：

```python
# ---------- 基本配置 ----------

# 要爬取的 UP 主 UID（主目标，如互动抽奖娘）
TARGET_UID = 3546776042736296

# 额外的汇总账号 UID（如其他的抽奖工具号）
# run 命令会依次处理 TARGET_UID 和此列表中的每个 UID
TARGET_UIDS = []

# 登录凭证（见下方获取方法）
CREDENTIAL = {
    "sessdata": "your_sessdata_here",
    "bili_jct": "your_bili_jct_here",
    "buvid3": "your_buvid3_here",
}

# ---------- 可选配置 ----------

# 动态最大时效（小时），超时的跳过，默认 168（7 天）
MAX_DYNAMIC_AGE_HOURS = 168

# 每次 run 最多参与最新 N 条动态中的抽奖，默认 2
MAX_DYNAMICS_TO_PROCESS = 2

# Server 酱推送（中奖通知 + Cookie 失效提醒），留空不启用
SERVERCHAN_SCKEY = ""

# 关注扫描时额外排除的作者 UID（如抽奖汇总工具号 100680137）
EXCLUDE_UIDS = []

# 关注流扫描条数上限，默认 500（约 25 页），关注量大可调大
FOLLOW_SCAN_LIMIT = 500
```

**获取 Cookie 方法**：登录哔哩哔哩后，F12 打开开发者工具，在 Network 面板找到任意请求，复制 Cookie 头即可。

## 使用

```bash
# 执行完整工作流（获取动态 → 分类 → 参与抽奖）
python fetch.py run

# 获取动态（仅爬取）
python fetch.py fetch <uid>

# 处理转发抽奖
python fetch.py forward

# 处理互动抽奖
python fetch.py interact

# 检测是否中奖
python fetch.py check-lottery

# 检查 Cookie 是否有效
python fetch.py check-cookie

# 参与关注动态流中的抽奖
python fetch.py follow

# 随机互动 N 条热门动态（默认 3）
python fetch.py random [N]

# 清理旧动态（预览，不删除）
python fetch.py clean --days 30

# 清理旧动态（跳过确认，直接删除）
python fetch.py clean --days 30 --confirm
```

## 青龙面板部署

### 1. 添加订阅（拉库）

青龙面板 → 订阅管理 → 新建订阅：

| 配置项 | 值 |
|--------|-----|
| 名称 | bilibili-lottery |
| 类型 | 公开仓库 |
| 仓库地址 | `https://github.com/你的用户名/bilibili-lottery.git` |
| 定时类型 | 手动（或按需设置，如 `0 6 * * *` 每天 6 点检查更新） |
| 白名单 | `fetch.py` |
| 文件后缀 | `.py` |

保存后点击「运行」拉取代码。后续仓库有更新时也会自动同步。

> 青龙面板 v2.10+ 的脚本目录为 `/ql/data/scripts/<仓库名>`，旧版本可能是 `/ql/repo`。

### 2. 安装依赖

青龙面板 → 依赖管理 → Python 依赖 → 添加：

```
bilibili-api
```

### 3. 配置文件

青龙面板 → 文件管理 → 进入 `bilibili-lottery` 目录 → 复制 `config.py.example` 为 `config.py` → 编辑并填入凭证。

或者通过终端：

```bash
cp /ql/data/scripts/bilibili-lottery/config.py.example /ql/data/scripts/bilibili-lottery/config.py
# 然后编辑 config.py，或直接用 cat 覆盖
cat > /ql/data/scripts/bilibili-lottery/config.py << 'CONFIGEOF'
TARGET_UID = 3546776042736296
TARGET_UIDS = [100680137]
CREDENTIAL = {
    "sessdata": "your_sessdata_here",
    "bili_jct": "your_bili_jct_here",
    "buvid3": "your_buvid3_here",
}
MAX_DYNAMIC_AGE_HOURS = 168
MAX_DYNAMICS_TO_PROCESS = 2
SERVERCHAN_SCKEY = ""
EXCLUDE_UIDS = [100680137]
FOLLOW_SCAN_LIMIT = 500
CONFIGEOF
```

> `config.py` 不会随仓库更新被覆盖（青龙只同步 `.py` 白名单）。

### 4. 添加定时任务

青龙面板 → 定时任务 → 添加任务：

| 任务名称 | 命令 | 定时规则 | 说明 |
|---------|------|---------|------|
| B站抽奖 | `cd /ql/data/scripts/bilibili-lottery && python fetch.py run` | `0 */2 * * *` | 每 2 小时，处理汇总账号的抽奖 |
| B站关注流 | `cd /ql/data/scripts/bilibili-lottery && python fetch.py follow` | `0 */6 * * *` | 每 6 小时，扫描关注流中零散抽奖 |
| B站防黑1 | `cd /ql/data/scripts/bilibili-lottery && python fetch.py random 2` | `30 9 * * *` | 每天 9:30，随机互动防黑号 |
| B站防黑2 | `cd /ql/data/scripts/bilibili-lottery && python fetch.py random 2` | `30 14 * * *` | 每天 14:30，随机互动防黑号 |
| B站防黑3 | `cd /ql/data/scripts/bilibili-lottery && python fetch.py random 2` | `30 20 * * *` | 每天 20:30，随机互动防黑号 |
| B站中奖检测 | `cd /ql/data/scripts/bilibili-lottery && python fetch.py check-lottery` | `0 9,21 * * *` | 每天 9 点、21 点 |
| B站Cookie检查 | `cd /ql/data/scripts/bilibili-lottery && python fetch.py check-cookie` | `0 8 * * *` | 每天 8 点 |
| B站清理旧动态 | `cd /ql/data/scripts/bilibili-lottery && python fetch.py clean --days 30 --confirm` | `0 3 1 * *` | 每月 1 号凌晨 3 点 |

**关于并发说明**：多个任务可能同时触发（如 9:00 中奖检测 + 9:30 随机互动），`python fetch.py` 内部没有分布式锁，但每个命令操作不同的 API 和数据文件，不会冲突。如果担心 API 频率，可以将部分任务的分钟偏移错开（如 `run` 改为 `5 */2 * * *`）。

**关于随机互动防黑**：`random 2` 会从 B 站热门动态中随机选 2 条进行转发/评论/点赞，模拟正常用户行为。固定在 9:30、14:30、20:30 三次，避免了全在整点扎堆。实际选取的动态是随机的，单一固定时间不会导致行为模式被识别。

## 工作流程

```
1. 获取动态
   └─ 调用 get_dynamic_page_list 获取 UP 主最新动态

2. 分类提取
   └─ 解析 opus 信息，按分类提取具体抽奖链接

3. 去重判断
   └─ participated.json - 已参与抽奖（唯一去重依据，已参与的永久跳过）
   └─ crawled_ids.json - 临时爬取缓存（仅用于 session 内复用，不屏蔽重新处理）

4. 自动参与
   └─ 解析抽奖要求（关注/转发/评论/点赞）
   └─ 按需执行各操作，失败重试 3 次，随机延迟 2-5 秒

5. 记录日志
   └─ logs/YYYY-MM-DD.log（保留 7 天）
```

## 项目结构

```
bilibili-lottery/
├── bilibili_lottery/
│   ├── __init__.py      # 包入口
│   ├── fetcher.py       # 动态获取
│   ├── classifier.py    # 抽奖分类提取
│   ├── parser.py        # 内容解析
│   ├── participant.py   # 参与抽奖
│   ├── notifier.py      # 中奖检测与推送
│   └── utils.py         # 工具函数
├── logs/                # 日志目录
├── dynamics/            # 动态数据
├── config.py.example    # 配置示例
├── requirements.txt
└── fetch.py             # CLI 入口
```

## 注意事项

- 凭证信息仅本地使用，不会上传
- 建议设置合理的任务间隔（如 30 分钟以上），避免触发风控
- 日志文件包含操作记录，可用于排查问题
- Cookie 有效期约 30 天，建议配置 `check-cookie` 定时任务并开启 Server 酱推送，失效时会收到提醒
