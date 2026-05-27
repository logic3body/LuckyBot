# bilibili-lottery

哔哩哔哩抽奖参与工具，自动获取 UP 主（如"互动抽奖娘"）的抽奖合集动态，分类提取转发抽奖、互动抽奖等链接，自动参与。

## 功能

- 自动获取 UP 主动态（支持去重）
- 分类提取：转发抽奖、充电抽奖、预约抽奖、互动抽奖
- 智能解析抽奖要求（关注/转发/评论/点赞）
- 失败重试机制（每操作 3 次重试）
- 完整操作日志（JSON Lines 格式）
- 定时任务支持（青龙面板等）

## 安装

```bash
# 克隆后安装依赖（需要 bilibili-api）
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
    "buvid3": "your_buvid3_here",
}
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
```

### 青龙面板配置

建议任务命令：
```bash
cd /path/to/bilibili-lottery && python fetch.py run
```

## 工作流程

```
1. 获取动态
   └─ 调用 get_dynamic_page_list 获取 UP 主最新动态

2. 分类提取
   └─ 解析 opus 信息，按分类提取具体抽奖链接

3. 去重判断
   └─ crawled_ids.json - 已爬取动态（保留最近 10 条）
   └─ participated.json - 已参与抽奖

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
│   ├── parser.py         # 内容解析
│   ├── participant.py   # 参与抽奖
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