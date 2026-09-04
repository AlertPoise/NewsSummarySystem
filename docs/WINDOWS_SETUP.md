# Windows 10/11 环境说明

安装 Python 3.11 x64 后，在 `backend` 目录执行 `py -3.11 -m venv .venv`，激活 `.venv\Scripts\Activate.ps1`，再执行 `pip install -r requirements.txt`。复制 `.env.example` 为 `.env` 并只在本机填写 `DB_PASSWORD`。

安装 MySQL 8.x，确认服务监听 127.0.0.1:3306。先在 `sql/create_database.sql` 的两个 `CHANGE_ME` 填入本机强密码，再以有建库权限的管理员执行 `scripts/init_database.ps1`；随后 `.env` 的密码必须一致。应用连接只使用 `news_app`。

使用 DevEco Studio 建立 HarmonyOS 工程的正式步骤由 E 在阶段 4 按 `frontend_harmony/README.md` 完成。后端阶段 1 可运行 `scripts/start_backend.ps1` 并访问 `/api/health`。Worker 在 D 阶段 3 实现、模型在阶段 2 验收后才可运行。

TODO(B-阶段2)：由 B 协调 C 根据最终 PyTorch、Transformers、显卡驱动和 CUDA 组合验证后补充正式安装命令；输入为训练与在线推理的真实环境验证结果，输出为 Windows 可复现安装命令，必须遵守 CNewSum 和性能验收要求。
