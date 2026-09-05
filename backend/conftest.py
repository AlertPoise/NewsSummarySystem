# backend/conftest.py
#
# 作用（端到端第二轮重跑发现的踩坑）：
#   pytest 解析 rootdir 时，会从测试文件目录（backend/tests）向上找最近的 conftest.py
#   作为 rootdir 标记，并把该 conftest 所在目录插入 sys.path。
#   当脚本从项目根目录（NewsSummarySystem-main）启动 pytest 时，没有 backend/conftest.py，
#   pytest 会把 backend/tests/ 当作 rootdir，sys.path 里就只有 backend/tests/，
#   而 app 包在 backend/app/，于是 `from app.database import Base` 抛 ModuleNotFoundError。
#
#   在 backend/ 放一个空 conftest.py 后，pytest 把 backend/ 当 rootdir，
#   sys.path 插入 backend/，`from app.database` 就能解析成功。
#
# 本身不需要任何 fixture：仅作为 pytest rootdir 锚点存在。