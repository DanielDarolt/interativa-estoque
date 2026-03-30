from flask import Flask, render_template, request, redirect
import psycopg
import os

from psycopg import cursor

app = Flask(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://interativa_user:Inte!rativa2025@localhost:5432/interativa_estoque"
)

def conectar():
    return psycopg.connect(DATABASE_URL)

def registrar_movimentacao(cursor, material_id, tipo_movimentacao, quantidade_movimentada,
                           estoque_antes, estoque_depois, projeto_id=None, observacao=None):
    cursor.execute("""
        INSERT INTO historico_movimentacao (
            material_id,
            projeto_id,
            tipo_movimentacao,
            quantidade_movimentada,
            estoque_antes,
            estoque_depois,
            observacao
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (
        material_id,
        projeto_id,
        tipo_movimentacao,
        quantidade_movimentada,
        estoque_antes,
        estoque_depois,
        observacao
    ))

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
        quantidade = int(request.form['quantidade'])

        cursor.execute("""
            INSERT INTO materiais (nome, espessura, quantidade)
            VALUES (%s, %s, %s)
            RETURNING id
        """, (nome, espessura, quantidade))

        material_id = cursor.fetchone()[0]

        registrar_movimentacao(
            cursor=cursor,
            material_id=material_id,
            tipo_movimentacao='entrada_manual',
            quantidade_movimentada=quantidade,
            estoque_antes=0,
            estoque_depois=quantidade,
            observacao='Cadastro inicial do material'
        )

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
        quantidade_nova = int(request.form['quantidade'])

        # Busca a quantidade antiga antes de atualizar
        cursor.execute("SELECT quantidade FROM materiais WHERE id = %s", (material_id,))
        resultado = cursor.fetchone()

        if not resultado:
            conn.close()
            return "Material não encontrado."

        quantidade_antiga = int(resultado[0])

        # Atualiza o material
        cursor.execute('''
            UPDATE materiais
            SET nome = %s, espessura = %s, quantidade = %s
            WHERE id = %s
        ''', (nome, espessura, quantidade_nova, material_id))

        # Só registra histórico se a quantidade mudou
        if quantidade_nova != quantidade_antiga:
            diferenca = abs(quantidade_nova - quantidade_antiga)

            registrar_movimentacao(
                cursor=cursor,
                material_id=material_id,
                tipo_movimentacao='ajuste_estoque',
                quantidade_movimentada=diferenca,
                estoque_antes=quantidade_antiga,
                estoque_depois=quantidade_nova,
                projeto_id=None,
                observacao='Ajuste manual na edição do material'
            )

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

    # Primeiro valida todo o estoque
    for material_id, qtd in materiais:
        cursor.execute("SELECT quantidade FROM materiais WHERE id = %s", (material_id,))
        resultado_estoque = cursor.fetchone()

        if not resultado_estoque:
            conn.close()
            return f"Material {material_id} não encontrado"

        estoque = int(resultado_estoque[0])

        if estoque < qtd:
            conn.close()
            return f"Estoque insuficiente para material {material_id}"

    # Depois faz as baixas e registra histórico
    for material_id, qtd in materiais:
        cursor.execute("SELECT quantidade FROM materiais WHERE id = %s", (material_id,))
        estoque_antes = int(cursor.fetchone()[0])

        estoque_depois = estoque_antes - int(qtd)

        cursor.execute('''
            UPDATE materiais
            SET quantidade = %s
            WHERE id = %s
        ''', (estoque_depois, material_id))

        registrar_movimentacao(
            cursor=cursor,
            material_id=material_id,
            tipo_movimentacao='producao_projeto',
            quantidade_movimentada=int(qtd),
            estoque_antes=estoque_antes,
            estoque_depois=estoque_depois,
            projeto_id=projeto_id,
            observacao='Baixa automática ao produzir projeto'
        )

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

# =========================
# HISTORICO
# =========================

@app.route('/historico')
def historico():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            h.id,
            m.nome,
            m.espessura,
            h.tipo_movimentacao,
            h.quantidade_movimentada,
            h.estoque_antes,
            h.estoque_depois,
            COALESCE(p.nome, '-') AS projeto_nome,
            COALESCE(h.observacao, '-') AS observacao,
            h.data_movimentacao
        FROM historico_movimentacao h
        JOIN materiais m ON h.material_id = m.id
        LEFT JOIN projetos p ON h.projeto_id = p.id
        ORDER BY h.id DESC
    """)

    dados = cursor.fetchall()
    conn.close()

    tipos_formatados = {
        "entrada_manual": "Entrada manual",
        "saida_manual": "Saída manual",
        "producao_projeto": "Produção",
        "ajuste_estoque": "Ajuste de estoque",
        "edicao_material": "Edição de material",
        "exclusao_material": "Exclusão de material"
    }

    historicos = []
    for item in dados:
        tipo_original = item[3]

        historicos.append({
            "id": item[0],
            "material": item[1],
            "espessura": item[2],
            "tipo": tipos_formatados.get(tipo_original, tipo_original),
            "quantidade_movimentada": item[4],
            "estoque_antes": item[5],
            "estoque_depois": item[6],
            "projeto": item[7],
            "observacao": item[8],
            "data": item[9].strftime("%d/%m/%Y %H:%M")
        })

    return render_template('historico.html', historicos=historicos)