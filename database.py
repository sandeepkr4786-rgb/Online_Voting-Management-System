import os
import sqlite3

# Try importing mysql.connector; if unavailable, SQLite will be used.
try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
    MYSQL_AVAILABLE = True
except ImportError:
    MySQLError = Exception
    MYSQL_AVAILABLE = False

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
SQLITE_DB_PATH = os.path.join(BASE_DIR, 'voting.db')

# MySQL Configuration (customize or set via environment variables)
MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
MYSQL_USER = os.getenv('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '1234')
MYSQL_DB = os.getenv('MYSQL_DB', 'voting_db')
DB_TYPE = os.getenv('DB_TYPE', 'auto').lower()  # 'auto', 'sqlite', or 'mysql'

class DBConnection:
    """Wrapper that normalizes SQLite and MySQL queries & cursor methods."""
    def __init__(self, backend, raw_conn):
        self.backend = backend  # 'sqlite' or 'mysql'
        self.conn = raw_conn
        self._cursor = None

    def cursor(self):
        self._cursor = DBCursor(self.backend, self.conn.cursor())
        return self._cursor

    def commit(self):
        self.conn.commit()

    def rollback(self):
        try:
            self.conn.rollback()
        except Exception:
            pass

    def close(self):
        try:
            if self._cursor:
                self._cursor.close()
            self.conn.close()
        except Exception:
            pass

class DBCursor:
    def __init__(self, backend, raw_cursor):
        self.backend = backend
        self.cursor = raw_cursor

    def execute(self, query, params=None):
        if self.backend == 'sqlite':
            # Convert %s placeholders to SQLite's ?
            sqlite_query = query.replace('%s', '?')
            if params is None:
                return self.cursor.execute(sqlite_query)
            return self.cursor.execute(sqlite_query, params)
        else:
            if params is None:
                return self.cursor.execute(query)
            return self.cursor.execute(query, params)

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    @property
    def lastrowid(self):
        return self.cursor.lastrowid

    def close(self):
        try:
            self.cursor.close()
        except Exception:
            pass

def init_db(conn):
    """Ensure all required tables exist."""
    cur = conn.cursor()
    if conn.backend == 'sqlite':
        cur.execute('''
            CREATE TABLE IF NOT EXISTS polls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS options (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                poll_id INTEGER NOT NULL,
                option_text TEXT NOT NULL,
                image_path TEXT DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (poll_id) REFERENCES polls(id) ON DELETE CASCADE
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS voters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                voter_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                age INTEGER NOT NULL,
                address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                poll_id INTEGER NOT NULL,
                option_id INTEGER NOT NULL,
                voter_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(poll_id, voter_id),
                FOREIGN KEY (poll_id) REFERENCES polls(id) ON DELETE CASCADE,
                FOREIGN KEY (option_id) REFERENCES options(id) ON DELETE CASCADE
            )
        ''')
    else:
        cur.execute('''
            CREATE TABLE IF NOT EXISTS polls (
                id INT AUTO_INCREMENT PRIMARY KEY,
                question VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS options (
                id INT AUTO_INCREMENT PRIMARY KEY,
                poll_id INT NOT NULL,
                option_text VARCHAR(255) NOT NULL,
                image_path VARCHAR(255) DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS voters (
                id INT AUTO_INCREMENT PRIMARY KEY,
                voter_id VARCHAR(50) NOT NULL UNIQUE,
                name VARCHAR(100) NOT NULL,
                age INT NOT NULL,
                address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS votes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                poll_id INT NOT NULL,
                option_id INT NOT NULL,
                voter_id VARCHAR(50) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_voter_poll (poll_id, voter_id)
            )
        ''')
    conn.commit()
    cur.close()

def get_db():
    """
    Returns a unified DBConnection.
    Supports auto-detection: tries MySQL first (if configured/available),
    and falls back cleanly to SQLite so the project runs out of the box with 0 setup!
    """
    # 1. Try MySQL if requested or auto
    if (DB_TYPE in ('mysql', 'auto')) and MYSQL_AVAILABLE:
        try:
            raw_conn = mysql.connector.connect(
                host=MYSQL_HOST,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DB,
                connect_timeout=2
            )
            conn = DBConnection('mysql', raw_conn)
            init_db(conn)
            return conn
        except MySQLError as err:
            if DB_TYPE == 'mysql':
                print(f"[Database Error] Could not connect to MySQL: {err}")
                return None
            # If auto, fallback quietly to SQLite
            print(f"[Database Notice] MySQL unavailable ({err}). Using built-in SQLite database.")

    # 2. SQLite fallback (always available in standard library)
    try:
        raw_conn = sqlite3.connect(SQLITE_DB_PATH)
        raw_conn.execute("PRAGMA foreign_keys = ON")
        conn = DBConnection('sqlite', raw_conn)
        init_db(conn)
        return conn
    except Exception as e:
        print(f"[Database Error] Could not open SQLite database: {e}")
        return None

