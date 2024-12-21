# sql_queries.py

#####################
# store表相关SQL
#####################

SELECT_ALL_STORE = """
    SELECT id, group_name, line_text 
      FROM store
     ORDER BY id ASC
"""

SELECT_STORE_BY_GROUP = """
    SELECT id, group_name, line_text 
      FROM store
     WHERE group_name = %s
     ORDER BY id ASC
"""

INSERT_STORE = """
    INSERT INTO store (group_name, line_text)
    VALUES (%s, %s)
"""

DELETE_STORE_BY_TEXT = """
    DELETE FROM store
     WHERE line_text = %s
"""

UPDATE_STORE_BY_TEXT = """
    UPDATE store
       SET line_text = %s
     WHERE id IN (
        SELECT id FROM store
         WHERE line_text = %s
         ORDER BY id ASC
         LIMIT 1
     )
"""

SELECT_ID_BY_TEXT = """
    SELECT id FROM store
     WHERE line_text = %s
     ORDER BY id ASC
     LIMIT 1
"""

UPDATE_STORE_LINE_TEXT_BY_ID = """
    UPDATE store
       SET line_text = %s
     WHERE id = %s
"""

#####################
# translations表相关SQL
#####################

SELECT_ALL_TRANSLATIONS = """
    SELECT original_text, translated_text 
      FROM translations
"""

INSERT_OR_UPDATE_TRANSLATION = """
    INSERT INTO translations (original_text, translated_text)
         VALUES (%s, %s)
    ON CONFLICT (original_text)
    DO UPDATE SET translated_text = EXCLUDED.translated_text
"""

DELETE_TRANSLATION_BY_ORIGINAL = """
    DELETE FROM translations
     WHERE original_text = %s
"""

#####################
# 其他可能的SQL...
#####################


