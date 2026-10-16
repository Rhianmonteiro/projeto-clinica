import sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session

app = Flask(__name__)
app.secret_key = 'clinica-vida-chave-local'
DB_PATH = 'clinica.db'

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, email TEXT NOT NULL UNIQUE, senha TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS medicos (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, crm TEXT NOT NULL UNIQUE, especialidade TEXT NOT NULL, telefone TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS pacientes (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, cpf TEXT NOT NULL UNIQUE, data_nascimento TEXT NOT NULL, telefone TEXT, endereco TEXT);
    CREATE TABLE IF NOT EXISTS agendamentos (id INTEGER PRIMARY KEY AUTOINCREMENT, paciente TEXT NOT NULL, medico TEXT NOT NULL, data TEXT NOT NULL, hora TEXT NOT NULL, descricao TEXT DEFAULT '');
    ''')
    # Compatibilidade com banco anterior que não tinha a coluna descricao.
    cols = [r['name'] for r in conn.execute('PRAGMA table_info(agendamentos)').fetchall()]
    if 'descricao' not in cols:
        conn.execute("ALTER TABLE agendamentos ADD COLUMN descricao TEXT DEFAULT ''")
    conn.commit()
    conn.close()

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'usuario_id' not in session:
            return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return wrapper

@app.route('/')
def index():
    return redirect(url_for('painel') if 'usuario_id' in session else url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    erro = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        senha = request.form.get('senha', '')
        conn = get_db_connection()
        usuario = conn.execute('SELECT * FROM usuarios WHERE lower(email)=? AND senha=?', (email, senha)).fetchone()
        conn.close()
        if usuario:
            session['usuario_id'] = usuario['id']
            session['usuario_nome'] = usuario['nome']
            return redirect(url_for('painel'))
        erro = 'E-mail ou senha inválidos.'
    return render_template('login.html', erro=erro)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/painel')
@login_required
def painel():
    conn = get_db_connection()
    totais = {
        'usuarios': conn.execute('SELECT COUNT(*) FROM usuarios').fetchone()[0],
        'medicos': conn.execute('SELECT COUNT(*) FROM medicos').fetchone()[0],
        'pacientes': conn.execute('SELECT COUNT(*) FROM pacientes').fetchone()[0],
        'agendamentos': conn.execute('SELECT COUNT(*) FROM agendamentos').fetchone()[0]
    }
    conn.close()
    return render_template('painel.html', totais=totais)

@app.route('/usuarios', methods=['GET', 'POST'])
@login_required
def usuarios():
    conn = get_db_connection()
    if request.method == 'POST':
        nome, email, senha = (request.form.get(k, '').strip() for k in ('nome', 'email', 'senha'))
        if not nome or not email or not senha:
            flash('Preencha todos os campos.', 'erro')
        else:
            try:
                conn.execute('INSERT INTO usuarios (nome,email,senha) VALUES (?,?,?)', (nome,email,senha))
                conn.commit(); flash('Usuário cadastrado com sucesso!', 'sucesso')
            except sqlite3.IntegrityError:
                flash('Este e-mail já está cadastrado.', 'erro')
    lista = conn.execute('SELECT id,nome,email FROM usuarios ORDER BY nome').fetchall()
    conn.close()
    return render_template('usuarios.html', usuarios=lista)

@app.route('/usuarios/excluir/<int:id>', methods=['POST', 'GET'])
@login_required
def deletar_usuario(id):
    if session.get('usuario_id') == id:
        flash('Não é possível excluir o usuário conectado.', 'erro')
    else:
        conn = get_db_connection(); conn.execute('DELETE FROM usuarios WHERE id=?', (id,)); conn.commit(); conn.close()
        flash('Usuário excluído.', 'sucesso')
    return redirect(url_for('usuarios'))

@app.route('/medicos', methods=['GET', 'POST'])
@login_required
def medicos():
    conn = get_db_connection()
    if request.method == 'POST':
        dados = [request.form.get(k, '').strip() for k in ('nome','crm','especialidade','telefone')]
        try:
            conn.execute('INSERT INTO medicos (nome,crm,especialidade,telefone) VALUES (?,?,?,?)', dados)
            conn.commit(); flash('Médico cadastrado com sucesso!', 'sucesso')
        except sqlite3.IntegrityError:
            flash('Este CRM já está cadastrado.', 'erro')
    lista = conn.execute('SELECT * FROM medicos ORDER BY nome').fetchall(); conn.close()
    return render_template('medicos.html', medicos=lista)

@app.route('/medicos/excluir/<int:id>', methods=['POST','GET'])
@login_required
def deletar_medico(id):
    conn = get_db_connection(); conn.execute('DELETE FROM medicos WHERE id=?', (id,)); conn.commit(); conn.close()
    flash('Médico excluído.', 'sucesso'); return redirect(url_for('medicos'))

@app.route('/pacientes')
@login_required
def pacientes():
    conn = get_db_connection(); lista = conn.execute('SELECT * FROM pacientes ORDER BY nome').fetchall(); conn.close()
    return render_template('pacientes.html', pacientes=lista)

@app.route('/pacientes/cadastrar', methods=['POST'])
@login_required
def cadastrar_paciente():
    dados = [request.form.get(k, '').strip() for k in ('nome','cpf','data_nascimento','telefone','endereco')]
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO pacientes (nome,cpf,data_nascimento,telefone,endereco) VALUES (?,?,?,?,?)', dados)
        conn.commit(); flash('Paciente cadastrado com sucesso!', 'sucesso')
    except sqlite3.IntegrityError:
        flash('Este CPF já está cadastrado.', 'erro')
    conn.close(); return redirect(url_for('pacientes'))

@app.route('/pacientes/editar/<int:id>', methods=['POST'])
@login_required
def editar_paciente(id):
    dados = [request.form.get(k, '').strip() for k in ('nome','cpf','data_nascimento','telefone','endereco')]
    conn = get_db_connection()
    try:
        conn.execute('UPDATE pacientes SET nome=?,cpf=?,data_nascimento=?,telefone=?,endereco=? WHERE id=?', (*dados,id))
        conn.commit(); flash('Paciente atualizado com sucesso!', 'sucesso')
    except sqlite3.IntegrityError:
        flash('Não foi possível atualizar: este CPF já está cadastrado.', 'erro')
    conn.close(); return redirect(url_for('pacientes'))

@app.route('/pacientes/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_paciente(id):
    conn = get_db_connection(); conn.execute('DELETE FROM pacientes WHERE id=?', (id,)); conn.commit(); conn.close()
    flash('Paciente excluído.', 'sucesso'); return redirect(url_for('pacientes'))

@app.route('/agendamentos', methods=['GET','POST'])
@login_required
def agendamentos():
    conn = get_db_connection()
    if request.method == 'POST':
        dados = [request.form.get(k, '').strip() for k in ('paciente','medico','data','hora','descricao')]
        # Impede conflito de horário para o mesmo médico.
        conflito = conn.execute('SELECT id FROM agendamentos WHERE medico=? AND data=? AND hora=?', (dados[1],dados[2],dados[3])).fetchone()
        if conflito:
            flash('Este médico já possui agendamento nesse dia e horário.', 'erro')
        else:
            conn.execute('INSERT INTO agendamentos (paciente,medico,data,hora,descricao) VALUES (?,?,?,?,?)', dados)
            conn.commit(); flash('Agendamento cadastrado com sucesso!', 'sucesso')
    lista = conn.execute('SELECT * FROM agendamentos ORDER BY data,hora').fetchall()
    medicos_lista = conn.execute('SELECT * FROM medicos ORDER BY nome').fetchall()
    conn.close(); return render_template('agendamentos.html', agendamentos=lista, medicos=medicos_lista, agendamento_edit=None)

@app.route('/agendamentos/editar/<int:id>', methods=['GET','POST'])
@login_required
def editar_agendamento(id):
    conn = get_db_connection()
    if request.method == 'POST':
        dados = [request.form.get(k, '').strip() for k in ('paciente','medico','data','hora','descricao')]
        conflito = conn.execute('SELECT id FROM agendamentos WHERE medico=? AND data=? AND hora=? AND id<>?', (*dados[1:4],id)).fetchone()
        if conflito:
            flash('Este médico já possui agendamento nesse dia e horário.', 'erro')
        else:
            conn.execute('UPDATE agendamentos SET paciente=?,medico=?,data=?,hora=?,descricao=? WHERE id=?', (*dados,id)); conn.commit()
            flash('Agendamento atualizado.', 'sucesso'); conn.close(); return redirect(url_for('agendamentos'))
    item = conn.execute('SELECT * FROM agendamentos WHERE id=?', (id,)).fetchone()
    lista = conn.execute('SELECT * FROM agendamentos ORDER BY data,hora').fetchall()
    medicos_lista = conn.execute('SELECT * FROM medicos ORDER BY nome').fetchall(); conn.close()
    if not item: return redirect(url_for('agendamentos'))
    return render_template('agendamentos.html', agendamentos=lista, medicos=medicos_lista, agendamento_edit=item)

@app.route('/agendamentos/excluir/<int:id>', methods=['POST','GET'])
@login_required
def deletar_agendamento(id):
    conn = get_db_connection(); conn.execute('DELETE FROM agendamentos WHERE id=?', (id,)); conn.commit(); conn.close()
    flash('Agendamento cancelado.', 'sucesso'); return redirect(url_for('agendamentos'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
