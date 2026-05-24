# 高考化学题库商业化改版设计

Date: 2026-05-24 | Status: approved

## 1. 目标

将现有 Flask 单体应用改造为可商用的高考化学题库系统：
- 取消爬虫，改为人工上传 PDF + AI 解析 + 后台审核
- 新增用户名密码登录 + 24小时试用 + 激活码 VIP 体系
- 查询页改为左右分栏布局，左侧筛选区可点击直接查询，右侧关键词搜索 + 卡片列表 + 分页
- 新增独立后台管理应用（上传、解析审核、激活码管理）

## 2. 技术选型

- **框架**: Flask 单体（复用现有模型和搜索逻辑）
- **数据库**: SQLite + WAL 模式（1000 用户规模足够）
- **认证**: Flask-Login + session
- **前端**: Jinja2 模板 + 原生 JS，不做前后端分离
- **付费**: 激活码/卡密系统，预留支付接口扩展点

## 3. 架构

### 模块拆分

```
app.py              # 应用入口，注册以下 Blueprint
auth.py             # /auth/*   登录/注册
vip.py              # /api/vip/* 激活码兑换/VIP状态
query_bp.py         # /api/*    题目查询 API
admin_bp.py         # /admin/*  后台管理
models.py           # 共享数据层
search.py           # 搜索逻辑
parser.py           # PDF 解析 + AI 提取
```

### 数据模型

新增表：

```sql
users (
  id TEXT PK, username TEXT UNIQUE, password_hash TEXT,
  is_admin INTEGER DEFAULT 0,
  trial_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  vip_expire_at TIMESTAMP,  -- NULL = 未开通VIP
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

activation_codes (
  id TEXT PK, code TEXT UNIQUE, vip_days INTEGER,
  created_by TEXT, used_by TEXT, used_at TIMESTAMP,
  is_used INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

现有 questions 表新增索引：
```sql
CREATE INDEX idx_q_year ON questions(year);
CREATE INDEX idx_q_province ON questions(province);
CREATE INDEX idx_q_type ON questions(q_type);
```

### VIP 逻辑

- 注册时 `trial_start = now()`，24 小时内可查看
- `vip_expire_at IS NULL AND now() - trial_start > 24h` → 不可查看，提示充值
- `vip_expire_at > now()` → 可查看（VIP 有效）
- 激活码兑换：`vip_expire_at = max(now(), vip_expire_at) + vip_days`

## 4. 接口设计

### 认证
- `POST /auth/login` — 登录
- `POST /auth/register` — 注册
- `GET /auth/logout` — 退出

### 查询（需 login + vip/trial）
- `GET /api/questions?year=&province=&q_type=&keyword=&page=1&size=15` — 分页查询
- `GET /api/question/<id>` — 题目详情
- `GET /api/filters` — 筛选选项及每项数量

### VIP
- `POST /api/vip/activate` — 激活码兑换
- `GET /api/vip/status` — VIP 状态

### 管理后台（需 admin）
- `GET /admin` — 管理首页
- `POST /admin/upload` — 上传 PDF
- `GET /admin/parse/<paper_id>` — 查看 AI 解析结果
- `POST /admin/parse/<paper_id>/confirm` — 确认入库
- `GET /admin/codes` — 激活码列表
- `POST /admin/codes/generate` — 批量生成激活码

## 5. 页面设计

### 查询页（index.html）— 左右分栏

**顶部导航**: Logo | 搜索区(可选) | 用户名/VIP状态/退出 | 管理入口(管理员可见)

**左侧 260px 筛选区**:
- 年份标签列表（每个带数量）
- 省份标签列表（每个带数量）
- 题型标签列表（每个带数量）
- 点击即筛选，支持多选叠加
- 底部显示已选条件和结果数

**右侧内容区**:
- 关键词搜索框 + 搜索按钮
- 排序切换
- 题目卡片列表（badge: 年份/省份/题型 + 题干预览 + 知识点标签 + 可展开答案）
- 底部分页栏：每页条数下拉(15/30/50, 默认15) + 页码 + 总数

### 登录页（login.html）
- 居中表单，用户名 + 密码
- "没有账号？去注册" 链接

### 注册页（register.html）
- 居中表单，用户名 + 密码 + 确认密码
- 注册成功自动登录，开始24小时试用

### 后台 — 上传页（admin/upload.html）
- 拖拽/点击上传 PDF，选填年份/省份/试卷类型
- 上传后自动触发 AI 解析，跳转到审核页

### 后台 — 审核页（admin/review.html）
- 左侧 PDF 预览，右侧解析出的题目列表
- 每道题可编辑（题干/选项/答案/解析/知识点）后确认入库
- 支持批量确认

### 后台 — 激活码管理（admin/codes.html）
- 生成激活码（输入天数、数量）
- 查看已生成/已使用/未使用的码列表

## 6. 权限控制

```python
from functools import wraps

def login_required(f):
    # 检查 session user_id

def vip_required(f):
    # login_required + 检查 trial 或 vip_expire_at

def admin_required(f):
    # login_required + 检查 is_admin
```

模板层也检查权限，未登录重定向登录页，非VIP看到"请充值"提示页。

## 7. 管理员初始化

首个管理员通过 CLI 脚本创建：
```bash
python create_admin.py <username> <password>
```
或手动在数据库中设置 `is_admin=1`。

## 8. 不再保留

- `crawler/` — 爬虫模块
- `discover_papers.py` — 试卷发现
- `fetch_paper.py` — 试卷下载
- `batch_fetch.py` — 批量爬取
- `import_from_hf.py` — HuggingFace 导入
- `pipeline.py` — 数据管道
- `paper_urls*.json` — 试卷 URL 配置
- `/api/search/semantic` — 语义搜索（实验性，FTS5 足够）
