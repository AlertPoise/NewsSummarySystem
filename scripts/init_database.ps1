param([Parameter(Mandatory = $true)][string]$MySqlExecutable)

# TODO(A-阶段1)：由 A 在本机提供 mysql.exe 的绝对路径并交互输入管理员密码；输入为 MySQL 客户端路径和 sql/create_database.sql，输出为 news_summary 结构，必须先将 SQL 中 CHANGE_ME 替换为仅本机使用的强密码并遵守 docs/WINDOWS_SETUP.md。
& $MySqlExecutable -u root -p < "$PSScriptRoot\..\sql\create_database.sql"
