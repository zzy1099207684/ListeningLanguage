 CREATE TABLE IF NOT EXISTS store (
     id SERIAL PRIMARY KEY,
     group_name TEXT,       -- 分组名，可为空
     line_text TEXT NOT NULL
 );

 CREATE TABLE IF NOT EXISTS translations (
     id SERIAL PRIMARY KEY,
     original_text TEXT NOT NULL UNIQUE,
     translated_text TEXT
 );

 CREATE TABLE IF NOT EXISTS setting (
     id SERIAL PRIMARY KEY,
     name TEXT UNIQUE NOT NULL,         -- 'index_top', 'edit_choose', 'combined_training' 等
     selected_groups TEXT              -- 存储选中的组列表，可用 JSON 或逗号分隔
 );