import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS materiais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT,
    espessura INTEGER,
    quantidade INTEGER
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS projetos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT,
    status TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS projeto_materiais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    projeto_id INTEGER,
    material_id INTEGER,
    quantidade INTEGER
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS historico (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id INTEGER,
    quantidade INTEGER,
    projeto_id INTEGER,
    data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

conn.commit()
conn.close()

print("Banco criado com sucesso!")