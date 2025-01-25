# sql_queries.py

#####################
# groups 表相关SQL
#####################

SELECT_ALL_GROUPS = """
    SELECT group_id, group_name 
      FROM groups
     ORDER BY group_id ASC
"""

SELECT_GROUP_BY_NAME = """
    SELECT group_id, group_name 
      FROM groups
     WHERE group_name = %s
     LIMIT 1
"""

INSERT_GROUP = """
    INSERT INTO groups (group_name)
    VALUES (%s)
    RETURNING group_id
"""

#####################
# store 表相关SQL
#####################

SELECT_ALL_STORE = """
    SELECT store_id, group_id, line_text
      FROM store
     ORDER BY store_id ASC
"""

SELECT_STORE_BY_GROUP_ID = """
    SELECT store_id, group_id, line_text
      FROM store
     WHERE group_id = %s
     ORDER BY store_id ASC
"""

INSERT_STORE = """
    INSERT INTO store (group_id, line_text)
    VALUES (%s, %s)
    RETURNING store_id
"""

DELETE_STORE_BY_ID = """
    DELETE FROM store
     WHERE store_id = %s
"""

UPDATE_STORE_BY_ID = """
    UPDATE store
       SET line_text = %s
     WHERE store_id = %s
"""

SELECT_STORE_BY_ID = """
    SELECT store_id, group_id, line_text
      FROM store
     WHERE store_id = %s
     LIMIT 1
"""

#####################
# translations 表相关SQL
#####################

SELECT_ALL_TRANSLATIONS = """
    SELECT store_id, translated_text
      FROM translations
"""

INSERT_OR_UPDATE_TRANSLATION = """
    INSERT INTO translations (store_id, translated_text)
    VALUES (%s, %s)
    ON CONFLICT (store_id)
    DO UPDATE SET translated_text = EXCLUDED.translated_text
"""

DELETE_TRANSLATION_BY_STORE_ID = """
    DELETE FROM translations
     WHERE store_id = %s
"""

SELECT_TRANSLATION_BY_STORE_ID = """
    SELECT translation_id, store_id, translated_text
      FROM translations
     WHERE store_id = %s
     LIMIT 1
"""

#####################
# setting 表相关SQL
#####################

UPSERT_SETTING = """
    INSERT INTO setting (setting_name, group_ids)
         VALUES (%s, %s)
    ON CONFLICT (setting_name)
    DO UPDATE SET group_ids = EXCLUDED.group_ids
"""

SELECT_SETTING_BY_NAME = """
    SELECT group_ids 
      FROM setting
     WHERE setting_name = %s
     LIMIT 1
"""
