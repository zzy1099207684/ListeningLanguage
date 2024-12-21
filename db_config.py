# db_config.py

DB_HOST = 'localhost'    # 主机
DB_USER = 'postgres'     # 用户名
DB_PASSWORD = 'root'     # 密码
DB_NAME = 'listing_language_db'         # 数据库名


# -- 对应 store.txt 的内容，改为存储在表 store
# CREATE TABLE IF NOT EXISTS store (
#     id SERIAL PRIMARY KEY,
#     group_name TEXT,       -- 分组名，可为空
#     line_text TEXT NOT NULL
# );
#
# -- 对应 translations.json 的内容，改为存储在表 translations
# CREATE TABLE IF NOT EXISTS translations (
#     id SERIAL PRIMARY KEY,
#     original_text TEXT NOT NULL UNIQUE,
#     translated_text TEXT
# );