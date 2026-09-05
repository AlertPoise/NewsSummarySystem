# Windows 环境搭建指南（从零到跑通后端）

> 适用对象：全体成员（A/B/C/D/E）在本机搭建开发环境。
> 前置条件：Windows 10/11，管理员权限（仅安装 MySQL 时需要）。
> 本文档与 `docs/DATABASE.md §13`（数据库初始化）、`docs/API.md §1`（健康检查契约）配套。

---

## 0. 前置软件清单

| 软件 | 版本要求 | 用途 | 检查命令 |
|---|---|---|---|
| Python | 3.11+（3.11-3.13 均可） | 后端 / 训练 / Worker | `python --version` |
| MySQL | 8.0.16+（CHECK 约束需 8.0.16 起） | 业务数据库 | `mysql --version` |

> 若 `python` / `mysql` 不在 PATH，先解决 PATH 再继续；或记住安装路径，后续步骤用绝对路径调用。

---

## 1. 初始化数据库（一次性）

```powershell
# 在仓库根目录执行
mysql -u root -p < sql\init_news_summary.sql
```

脚本做四件事：建库 `news_summary`、建应用账户 `news_app`（初始密码 `CHANGE_ME`）、授权、建 4 张表（可重复执行）。

然后**立即改密**（把 `<强密码>` 换成你本机自定义密码）：

```sql
ALTER USER 'news_app'@'localhost' IDENTIFIED BY '<强密码>';
ALTER USER 'news_app'@'127.0.0.1' IDENTIFIED BY '<强密码>';
FLUSH PRIVILEGES;
```

> 也可以用交互式脚本代替上面两步：`powershell -ExecutionPolicy Bypass -File scripts\init_database.ps1`

连接参数（写连接卡上）：`Host=127.0.0.1`、`Port=3306`、`Database=news_summary`、`User=news_app`。

---

## 2. Python 虚拟环境与依赖

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

> **轻量安装（可选）**：`requirements.txt` 含 `torch`/`transformers`（约 2 GB+，仅 B/C 的训练与推理需要）。
> A/D/E 若只做 API 与数据层开发，可临时只装轻量子集：
>
> ```powershell
> pip install fastapi "uvicorn[standard]" sqlalchemy pymysql pydantic-settings python-dotenv httpx pytest
> ```
>
> 联调阶段（阶段 5）前必须补齐全量依赖。

---

## 3. 配置 backend/.env

```powershell
copy .env.example .env
```

编辑 `.env`，至少填写：

| 键 | 值 |
|---|---|
| `DB_PASSWORD` | 第 1 步设置的新闻账户强密码 |

其余 `CHANGE_ME` 项（BERT_MODEL_NAME、SUMMARIZER_MODEL_NAME、MODEL_VERSION 等）由 B/C 在阶段 2 交付后填写，A/D/E 前期无需理会。

> `.env` 已被 `.gitignore` 排除，**禁止提交真实密码**。

---

## 4. 启动后端

```powershell
# 方式一：脚本（若提示执行策略限制，先执行下面这行）
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
..\scripts\start_backend.ps1

# 方式二：手动
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## 5. 验证跑通（两步冒烟）

```powershell
# 5.1 健康检查 —— 期望 {"code":0,...,"data":{"status":"healthy"}}
curl http://127.0.0.1:8000/api/health

# 5.2 错误码链路 —— 缺失 X-Client-ID 期望 {"code":1001,...}
curl -X POST http://127.0.0.1:8000/api/favorites/1
```

两条都符合预期即环境就绪。业务接口（收藏/反馈/新闻）在阶段 3 实现前调用会返回 501/未实现，属正常现象。

---

## 6. 常见问题

| 现象 | 原因与处理 |
|---|---|
| `mysql` 不是内部或外部命令 | 未加入 PATH；用安装目录绝对路径，如 `F:\mysql-8.0.45-winx64\bin\mysql.exe` |
| CHECK 约束不生效 | MySQL < 8.0.16；升级 MySQL |
| `Access denied for user 'news_app'` | `.env` 的 `DB_PASSWORD` 与第 1 步 ALTER USER 设置的不一致，或只改了 `localhost` 没改 `127.0.0.1` |
| 端口 8000 被占用 | `netstat -ano \| findstr 8000` 找到 PID 后结束进程，或改用 `--port 8001`（同时改 `.env` 的 `APP_PORT`） |
| PowerShell 拒绝运行 .ps1 | 见第 4 节执行策略命令；只影响当前窗口 |
| 中文乱码 | 确认 MySQL 连接走 utf8mb4（`.env` 的 `DB_CHARSET` 默认已是） |

---

## 7. 角色差异速查

| 角色 | 必须装 | 可后装 |
|---|---|---|
| A（架构/API） | 全流程第 1-5 步 | torch/transformers |
| B（训练） | 第 1-3 步 + 全量依赖 + CNewSum 数据集（不入 Git） | — |
| C（AI 推理） | 第 1-3 步 + 全量依赖 | — |
| D（爬虫/Worker） | 第 1-5 步 + 全量依赖（Worker 要加载 Pipeline） | — |
| E（HarmonyOS） | 无需本指南；只需后端同学提供 `http://<后端IP>:8000` | — |

> E 直连后端时，启动方需把 uvicorn 的 `--host 0.0.0.0` 保持默认并在防火墙放行 8000 端口（仅联调阶段）。
