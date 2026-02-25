import sqlite3

DB_PATH = 'servers.db'

def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS servers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            host TEXT NOT NULL,
            port INTEGER NOT NULL DEFAULT 5000,
            username TEXT,
            password TEXT,
            description TEXT,
            tags TEXT,
            status TEXT DEFAULT 'offline',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 检查 tags 列是否存在（针对旧数据库）
    try:
        c.execute('SELECT tags FROM servers LIMIT 1')
    except sqlite3.OperationalError:
        c.execute('ALTER TABLE servers ADD COLUMN tags TEXT')
        
    # 创建工作流表
    c.execute('''
        CREATE TABLE IF NOT EXISTS workflows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            data TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 创建全局变量表
    c.execute('''
        CREATE TABLE IF NOT EXISTS global_variables (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
        
    conn.commit()
    conn.close()

def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
