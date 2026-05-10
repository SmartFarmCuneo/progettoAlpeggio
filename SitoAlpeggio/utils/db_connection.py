import pymysql
import os

# Database connection

def get_db_connection():
    """Connection to MySQL"""
    
    """return pymysql.connect(
        host='localhost',
        user='root',
        password='',
        database='irrigazione',
        cursorclass=pymysql.cursors.DictCursor
    )"""
    
    
    return pymysql.connect(
        host=os.getenv("DB_HOST", 'localhost'),
        user=os.getenv("DB_USER", 'root'),
        password=os.getenv("DB_PASSWORD", ''),
        database=os.getenv("DB_NAME", 'irrigazione'),
        cursorclass=pymysql.cursors.DictCursor
    )
