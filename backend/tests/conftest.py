import os

# 测试默认使用内存 sqlite；须在任何 app.* 模块导入前设置，
# 因为 app.database 在导入时即按 settings.database_url 创建 engine。
os.environ.setdefault("DATABASE_URL", "sqlite://")
