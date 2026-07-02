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

1. 复制 `config.py.example` 为 `config.py`
2. 填写你的 UID 和 Cookie 凭证：

```python
TARGET_UID = 3546776042736296
CREDENTIAL = {
    "sessdata": "your_sessdata_here",
    "bili_jct": "your_bili_jct_here",
    "buvid3": "your_bili_jct_here",
}

# 动态最大时效（小时），超过此时间发布的动态将被跳过，默认 168（7 天）
MAX_DYNAMIC_AGE_HOURS = 168

# 每次 run 最多参与最新 N 条动态中的抽奖，默认 2
MAX_DYNAMICS_TO_PROCESS = 2

# 可选：Server 酱推送（中奖通知 + Cookie 失效提醒）
SERVERCHAN_SCKEY = ""
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

# 随机互动 N 条热门动态（默认 3）
python fetch.py random [N]

# 清理旧动态（预览，不删除）
python fetch.py clean --days 30

# 清理旧动态（跳过确认，直接删除）
python fetch.py clean --days 30 --confirm
```

## 青龙面板部署

### 1. 拉取代码

```bash
cd /ql/data/scripts
git clone https://github.com/your-username/bilibili-lottery.git
cd bilibili-lottery
pip install -r requirements.txt
```

> 青龙面板 v2.10+ 的脚本目录为 `/ql/data/scripts`，旧版本可能是 `/ql/repo`，请根据实际版本调整。

### 2. 配置文件

```bash
cp config.py.example config.py
# 编辑 config.py，填入你的 TARGET_UID 和 CREDENTIAL
```

在青龙面板中可以通过「文件管理」直接编辑 `config.py`，或通过终端：

```bash
cat > /ql/data/scripts/bilibili-lottery/config.py << 'EOF'
TARGET_UID = 3546776042736296
CREDENTIAL = {
    "sessdata": "your_sessdata_here",
    "bili_jct": "your_bili_jct_here",
    "buvid3": "your_bili_jct_here",
}
SERVERCHAN_SCKEY = ""
EOF
```

### 3. 添加定时任务

进入青龙面板「定时任务」页面，添加以下任务：

| 任务名称 | 命令 | 定时规则 |
|---------|------|---------|
| B站抽奖 | `cd /ql/data/scripts/bilibili-lottery && python fetch.py run` | `0 */30 * * *`（每 30 分钟） |
| B站中奖检测 | `cd /ql/data/scripts/bilibili-lottery && python fetch.py check-lottery` | `0 9,21 * * *`（每天 9 点、21 点） |
| B站Cookie检查 | `cd /ql/data/scripts/bilibili-lottery && python fetch.py check-cookie` | `0 8 * * *`（每天 8 点） |
| B站清理旧动态 | `cd /ql/data/scripts/bilibili-lottery && python fetch.py clean --days 30 --confirm` | `0 3 1 * *`（每月 1 号凌晨 3 点） |

### 4. 依赖安装问题

如果青龙面板中 `pip install` 权限不足，可以尝试：

```bash
pip install -r requirements.txt --user
# 或指定 Python 路径
/ql/data/scripts/bilibili-lottery/.venv/bin/pip install -r requirements.txt
```

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
