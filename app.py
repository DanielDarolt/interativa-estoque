from flask import Flask, render_template, request, redirect
import psycopg
import os

app = Flask(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://interativa_user:Inte!rativa2025@localhost:5432/interativa_estoque"
)

def conectar():
    return psycopg.connect(DATABASE_URL)

@app.route('/')
def index():
    return render_template('index.html')

# =========================
# MATERIAIS
# =========================
@app.route('/materiais', methods=['GET', 'POST'])
def materiais():
    conn = conectar()
    cursor = conn.cursor()

    if request.method == 'POST':
        nome = request.form['nome']
        espessura = request.form['espessura']
        quantidade = request.form['quantidade']

        cursor.execute('''
            INSERT INTO materiais (nome, espessura, quantidade)
            VALUES (%s, %s, %s)
        ''', (nome, espessura, quantidade))
        conn.commit()

    cursor.execute('SELECT * FROM materiais ORDER BY id')
    dados = cursor.fetchall()
    conn.close()

    return render_template('materiais.html', materiais=dados)

# =========================
# EDITAR MATERIAL
# =========================
@app.route('/editar_material/<int:material_id>', methods=['GET', 'POST'])
def editar_material(material_id):
    conn = conectar()
    cursor = conn.cursor()

    if request.method == 'POST':
        nome = request.form['nome']
        espessura = request.form['espessura']
        quantidade = request.form['quantidade']

        cursor.execute('''
            UPDATE materiais
            SET nome = %s, espessura = %s, quantidade = %s
            WHERE id = %s
        ''', (nome, espessura, quantidade, material_id))

        cursor.execute('''
            INSERT INTO historico (material_id, quantidade, projeto_id)
            VALUES (%s, %s, NULL)
        ''', (material_id, quantidade))

        conn.commit()
        conn.close()

        return redirect('/materiais')

    cursor.execute("SELECT * FROM materiais WHERE id = %s", (material_id,))
    material = cursor.fetchone()

    conn.close()

    return render_template('editar_material.html', material=material)

# =========================
# EXCLUIR MATERIAL
# =========================
@app.route('/excluir_material/<int:material_id>')
def excluir_material(material_id):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM historico WHERE material_id = %s", (material_id,))
    cursor.execute("DELETE FROM projeto_materiais WHERE material_id = %s", (material_id,))
    cursor.execute("DELETE FROM materiais WHERE id = %s", (material_id,))

    conn.commit()
    conn.close()

    return redirect('/materiais')

# =========================
# PROJETOS
# =========================
@app.route('/projetos', methods=['GET', 'POST'])
def projetos():
    conn = conectar()
    cursor = conn.cursor()

    if request.method == 'POST':
        nome = request.form['nome']
        material_id = request.form['material_id']
        quantidade = request.form['quantidade']

        cursor.execute('''
            INSERT INTO projetos (nome, status)
            VALUES (%s, %s)
            RETURNING id
        ''', (nome, 'pendente'))

        projeto_id = cursor.fetchone()[0]

        cursor.execute('''
            INSERT INTO projeto_materiais (projeto_id, material_id, quantidade)
            VALUES (%s, %s, %s)
        ''', (projeto_id, material_id, quantidade))

        conn.commit()

    cursor.execute('SELECT * FROM projetos ORDER BY id')
    projetos = cursor.fetchall()

    cursor.execute('SELECT * FROM materiais ORDER BY id')
    materiais = cursor.fetchall()

    conn.close()

    return render_template('projetos.html', projetos=projetos, materiais=materiais)

# adicionar material ao projeto
@app.route('/add_material_projeto', methods=['POST'])
def add_material_projeto():
    projeto_id = request.form['projeto_id']
    material_id = request.form['material_id']
    quantidade = request.form['quantidade']

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO projeto_materiais (projeto_id, material_id, quantidade)
        VALUES (%s, %s, %s)
    ''', (projeto_id, material_id, quantidade))

    conn.commit()
    conn.close()

    return redirect('/projetos')

# =========================
# PRODUÇÃO
# =========================
@app.route('/produzir/<int:projeto_id>')
def produzir(projeto_id):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT status FROM projetos WHERE id = %s", (projeto_id,))
    result = cursor.fetchone()

    if not result:
        conn.close()
        return "Projeto não encontrado"

    status = result[0]

    if status == "produzido":
        conn.close()
        return "Projeto já produzido!"

    cursor.execute('''
        SELECT material_id, quantidade
        FROM projeto_materiais
        WHERE projeto_id = %s
    ''', (projeto_id,))
    materiais = cursor.fetchall()

    for material_id, qtd in materiais:
        cursor.execute("SELECT quantidade FROM materiais WHERE id = %s", (material_id,))
        estoque = cursor.fetchone()[0]

        if estoque < qtd:
            conn.close()
            return f"Estoque insuficiente para material {material_id}"

    for material_id, qtd in materiais:
        cursor.execute('''
            UPDATE materiais
            SET quantidade = quantidade - %s
            WHERE id = %s
        ''', (qtd, material_id))

        cursor.execute('''
            INSERT INTO historico (material_id, quantidade, projeto_id)
            VALUES (%s, %s, %s)
        ''', (material_id, qtd, projeto_id))

    cursor.execute('''
        UPDATE projetos
        SET status = %s
        WHERE id = %s
    ''', ('produzido', projeto_id))

    conn.commit()
    conn.close()

    return redirect('/projetos')

# =========================
# EXCLUIR PROJETO
# =========================
@app.route('/excluir_projeto/<int:projeto_id>')
def excluir_projeto(projeto_id):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT status FROM projetos WHERE id = %s", (projeto_id,))
    result = cursor.fetchone()

    if not result:
        conn.close()
        return "Projeto não encontrado"

    status = result[0]

    if status == "produzido":
        cursor.execute('''
            SELECT material_id, quantidade
            FROM projeto_materiais
            WHERE projeto_id = %s
        ''', (projeto_id,))
        materiais = cursor.fetchall()

        for material_id, qtd in materiais:
            cursor.execute('''
                UPDATE materiais
                SET quantidade = quantidade + %s
                WHERE id = %s
            ''', (qtd, material_id))

            cursor.execute('''
                INSERT INTO historico (material_id, quantidade, projeto_id)
                VALUES (%s, %s, %s)
            ''', (material_id, qtd, projeto_id))

    cursor.execute("DELETE FROM projeto_materiais WHERE projeto_id = %s", (projeto_id,))
    cursor.execute("DELETE FROM projetos WHERE id = %s", (projeto_id,))

    conn.commit()
    conn.close()

    return redirect('/projetos')

# =========================
# ESTOQUE
# =========================
@app.route('/estoque')
def estoque():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM materiais ORDER BY id')
    materiais = cursor.fetchall()

    conn.close()

    return render_template('estoque.html', materiais=materiais)

# =========================

if __name__ == '__main__':
    app.run(debug=True)