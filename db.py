from flask import g
import pymysql
import os

def get_db():
    if 'db' not in g:
        g.db = pymysql.connect(
            host=os.getenv("MYSQL_HOST", "localhost"),
            user=os.getenv("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD", ""),
            database=os.getenv("MYSQL_DB", "chip_safety"),
            port=int(os.getenv("MYSQL_PORT", 3306)),
            cursorclass=pymysql.cursors.DictCursor
        )
    return g.db

def assign_project_to_user(project_id, user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE projects SET owner_id = %s WHERE id = %s", (user_id, project_id))
    conn.commit()
    cur.close()


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

