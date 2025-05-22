# Importação de bibliotecas necessárias para o funcionamento da aplicação
from flask import Flask, jsonify, render_template, request, redirect, url_for, flash, session, Response
import pyodbc
import bcrypt
from datetime import date, datetime, timedelta
import csv
from io import StringIO
from calendar import monthrange
import calendar
import socket
import pytz
import signal  # Para manipular sinais de encerramento
import sys  # Para encerrar a aplicação
import logging  # Para adicionar logs detalhados
from flask import jsonify


        #################      OBSERVAÇÕES EU RETIREI A CONECÇÃO REAL POR MOTIVOS DE SEGRANÇA ####################



# Configuração de logging para debug
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Inicialização da aplicação Flask
app = Flask(__name__)
app.secret_key = "supersecretkey123"

# Função para conectar ao banco de dados SQL Server
def get_db_connection():
    conn_str = (
        "DADOSFICTICIOS;"    #NOME DO BANCO 
        "SERVER=localhost;"   #CAMINHO DO SERVIDOR
        "DATABASE=FICCAO;" #NOME DO BANCO
        "Trusted_Connection=yes;"
    )
    return pyodbc.connect(conn_str, autocommit=False)

# Função para inicializar o banco de dados e criar tabelas necessárias
def initialize_database():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'transacoes')
            CREATE TABLE transacoes (
                id_transacao INT PRIMARY KEY IDENTITY(1,1),
                tipo_transacao VARCHAR(20) NOT NULL,
                valor DECIMAL(10, 2) NOT NULL,
                data_hora DATETIME DEFAULT GETDATE(),
                usuario_id INT NOT NULL,
                descricao VARCHAR(255),
                banco_pagamento VARCHAR(50),
                forma_pagamento VARCHAR(50),
                dono_transacao VARCHAR(50)
            );
        """)

        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'caixa_inicial')
            CREATE TABLE caixa_inicial (
                id_caixa INT PRIMARY KEY IDENTITY(1,1),
                valor_inicial DECIMAL(10, 2) NOT NULL,
                data_abertura DATE NOT NULL,
                usuario_id INT NOT NULL
            );
        """)

        conn.commit()
        cursor.close()
        conn.close()
        return True

    except pyodbc.Error as e:
        logging.error(f"Erro ao conectar ou inicializar o banco de dados: {e}")
        raise Exception(f"Falha na inicialização do banco de dados: {str(e)}")
    except Exception as e:
        logging.error(f"Erro inesperado na inicialização do banco: {e}")
        raise Exception(f"Erro inesperado: {str(e)}")

# Inicializa o banco de dados ao iniciar a aplicação
try:
    if not initialize_database():
        raise Exception("Falha ao inicializar o banco de dados.")
except Exception as e:
    logging.error(f"Não foi possível iniciar a aplicação devido a: {e}")
    exit(1)

# Função para obter a data e hora atual no fuso horário de São Paulo
def get_current_datetime():
    tz = pytz.timezone('America/Sao_Paulo')
    current_time = datetime.now(tz)
    return current_time.strftime('%d/%m/%Y %H:%M')

# Função para verificar se uma porta de rede está em uso
def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

# Define uma senha fixa e seu hash para autenticação (não recomendado para produção)
SENHA_FIXA = "123".encode('utf-8')
SENHA_HASH = bcrypt.hashpw(SENHA_FIXA, bcrypt.gensalt())
USUARIO_VALIDO = "admin"

# Rota para a página de login (raiz da aplicação)
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login = request.form['login']
        senha = request.form['senha'].encode('utf-8')
        if login == USUARIO_VALIDO and bcrypt.checkpw(senha, SENHA_HASH):
            session['usuario_id'] = 1
            session['redirect_count'] = 0  # Inicializa o contador de redirecionamentos
            flash('Login bem-sucedido!', 'success')
            return redirect(url_for('entrada'))
        else:
            flash('Credenciais inválidas. Tente novamente.', 'error')
    return render_template('login.html', current_datetime=get_current_datetime())

# Rota para a página de entradas
@app.route('/entrada', methods=['GET', 'POST'])
def entrada():
    # Verifica se o usuário está logado
    if 'usuario_id' not in session:
        flash('Por favor, faça login para continuar.', 'error')
        return redirect(url_for('login'))

    # Inicializa ou incrementa o contador de redirecionamentos na sessão
    session['redirect_count'] = session.get('redirect_count', 0) + 1
    if session['redirect_count'] > 5:  # Limite de 5 redirecionamentos
        logging.error("Loop de redirecionamento detectado na rota /entrada")
        return render_template('error.html', message="Erro: Loop de redirecionamento detectado. Por favor, verifique os logs."), 500

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Consultar o valor inicial do dia atual para o usuário logado
        data_atual = datetime.now().date()
        cursor.execute(
            "SELECT valor_inicial FROM caixa_inicial WHERE usuario_id = ? AND data_abertura = ?",
            (session['usuario_id'], data_atual)
        )
        valor_inicial_row = cursor.fetchone()
        valor_inicial = float(valor_inicial_row[0]) if valor_inicial_row else 0.00  # Default para 0 se não houver registro

        if request.method == 'POST':
            if 'valor_inicial' in request.form:
                valor = float(request.form['valor_inicial'])
                if valor < 0:
                    flash('O valor inicial da caixa não pode ser negativo.', 'error')
                    session['redirect_count'] = 0  # Redefinir o contador
                    return redirect(url_for('entrada'))

                # Verificar se já existe um registro para o dia atual
                cursor.execute(
                    "SELECT id_caixa FROM caixa_inicial WHERE usuario_id = ? AND data_abertura = ?",
                    (session['usuario_id'], data_atual)
                )
                existing_record = cursor.fetchone()
                if existing_record:
                    # Atualizar o valor existente
                    cursor.execute(
                        "UPDATE caixa_inicial SET valor_inicial = ? WHERE id_caixa = ?",
                        (valor, existing_record[0])
                    )
                else:
                    # Inserir novo registro
                    cursor.execute(
                        "INSERT INTO caixa_inicial (valor_inicial, data_abertura, usuario_id) VALUES (?, ?, ?)",
                        (valor, data_atual, session['usuario_id'])
                    )
                conn.commit()
                flash('Valor inicial da caixa atualizado com sucesso!', 'success')
                session['redirect_count'] = 0  # Redefinir o contador
                return redirect(url_for('entrada'))

            else:
                tipo = request.form['tipo']
                valor_str = request.form['valor']
                try:
                    valor = float(valor_str) if valor_str.strip() else 0.0
                    if valor <= 0:
                        flash('O valor da entrada deve ser maior que zero.', 'error')
                        session['redirect_count'] = 0  # Redefinir o contador
                        return redirect(url_for('entrada'))
                except ValueError:
                    flash('Valor inválido. Por favor, preencha corretamente.', 'error')
                    session['redirect_count'] = 0  # Redefinir o contador
                    return redirect(url_for('entrada'))
                descricao = request.form.get('descricao', '')
                banco_pagamento = request.form.get('banco_pagamento')
                dono_transacao = request.form.get('dono_transacao')
                cursor.execute(
                    "INSERT INTO transacoes (tipo_transacao, valor, data_hora, usuario_id, descricao, banco_pagamento, dono_transacao) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (tipo, valor, datetime.now(), session['usuario_id'], descricao, banco_pagamento, dono_transacao)
                )
                conn.commit()
                flash('Entrada registrada com sucesso!', 'success')
                session['redirect_count'] = 0  # Redefinir o contador
                return redirect(url_for('entrada'))

        # Consulta transações apenas do dia atual
        cursor.execute(
            "SELECT tipo_transacao, valor, data_hora, banco_pagamento, dono_transacao, id_transacao FROM transacoes WHERE usuario_id = ? AND CAST(data_hora AS DATE) = ? ORDER BY data_hora DESC",
            (session['usuario_id'], data_atual)
        )
        transacoes = cursor.fetchall()
        pix = [t for t in transacoes if t[0] == 'pix']
        cartao = [t for t in transacoes if t[0] == 'cartao']
        cedula = [t for t in transacoes if t[0] == 'cedula']
        geral = transacoes

        # Calcular totais e converter para float
        total_pix = float(sum(t[1] for t in pix))
        total_cartao = float(sum(t[1] for t in cartao))
        total_cedula = float(sum(t[1] for t in cedula))
        total_vendas = total_pix + total_cartao + total_cedula

        # Consultar despesas (saídas) apenas para tipo 'dinheiro' do dia atual
        cursor.execute(
            "SELECT SUM(valor) FROM transacoes WHERE tipo_transacao = 'saida' AND usuario_id = ? AND forma_pagamento = 'dinheiro' AND CAST(data_hora AS DATE) = ?",
            (session['usuario_id'], data_atual)
        )
        total_despesa = cursor.fetchone()[0] or 0.00
        total_despesa = float(abs(total_despesa))

        # Calcular saldo líquido (usando o valor_inicial recuperado)
        saldo = total_vendas - valor_inicial - total_despesa

        # Lista de dias da semana em português
        dias_semana = ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo']
        session['redirect_count'] = 0  # Redefinir o contador após renderizar
        return render_template(
            'entrada.html',
            pix=pix,
            cartao=cartao,
            cedula=cedula,
            geral=geral,
            dias_semana=dias_semana,
            current_datetime=get_current_datetime(),
            valor_inicial=valor_inicial,  # Passar o valor recuperado
            total_vendas=total_vendas,
            total_despesa=total_despesa,
            saldo=saldo
        )

    except Exception as e:
        logging.error(f'Erro ao processar entrada: {str(e)}')
        return render_template('error.html', message=f"Erro ao processar entrada: {str(e)}"), 500
    finally:
        cursor.close()
        conn.close()

# Rota para processar o fechamento do caixa
@app.route('/fechar_caixa', methods=['GET'])
def fechar_caixa():
    if 'usuario_id' not in session:
        flash('Por favor, faça login para continuar.', 'error')
        return redirect(url_for('login'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Consulta transações apenas do dia atual
        data_atual = datetime.now().date()
        cursor.execute(
            "SELECT tipo_transacao, valor, data_hora, banco_pagamento, dono_transacao, id_transacao FROM transacoes WHERE usuario_id = ? AND CAST(data_hora AS DATE) = ? ORDER BY data_hora DESC",
            (session['usuario_id'], data_atual)
        )
        transacoes = cursor.fetchall()
        pix = [t for t in transacoes if t[0] == 'pix']
        cartao = [t for t in transacoes if t[0] == 'cartao']
        cedula = [t for t in transacoes if t[0] == 'cedula']

        # Consultar o valor inicial do dia atual
        cursor.execute(
            "SELECT valor_inicial FROM caixa_inicial WHERE usuario_id = ? AND data_abertura = ?",
            (session['usuario_id'], data_atual)
        )
        valor_inicial_row = cursor.fetchone()
        valor_inicial = float(valor_inicial_row[0]) if valor_inicial_row else 0.00  # Default para 0 se não houver registro

        # Calcular totais e converter para float
        total_pix = float(sum(t[1] for t in pix))
        total_cartao = float(sum(t[1] for t in cartao))
        total_cedula = float(sum(t[1] for t in cedula))
        total_vendas = total_pix + total_cartao + total_cedula

        # Consultar despesas (saídas) apenas para tipo 'dinheiro' do dia atual
        cursor.execute(
            "SELECT SUM(valor) FROM transacoes WHERE tipo_transacao = 'saida' AND usuario_id = ? AND forma_pagamento = 'dinheiro' AND CAST(data_hora AS DATE) = ?",
            (session['usuario_id'], data_atual)
        )
        total_despesa = cursor.fetchone()[0] or 0.00
        total_despesa = float(abs(total_despesa))

        # Calcular saldo líquido
        saldo = total_vendas - valor_inicial - total_despesa

        # Lista de dias da semana em português
        dias_semana = ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo']
        dia_semana = dias_semana[data_atual.weekday()]

        return render_template(
            'fechar_caixa.html',
            data=data_atual.strftime('%d/%m/%Y'),
            dia_semana=dia_semana,
            total_pix=total_pix,
            total_cartao=total_cartao,
            total_cedula=total_cedula,
            valor_inicial=valor_inicial,
            total_vendas=total_vendas,
            total_despesa=total_despesa,
            saldo=saldo
        )

    except Exception as e:
        logging.error(f'Erro ao fechar caixa: {str(e)}')
        return render_template('error.html', message=f"Erro ao fechar caixa: {str(e)}"), 500
    finally:
        cursor.close()
        conn.close()
@app.route('/ver_transacoes', methods=['GET'])
def ver_transacoes():
    if 'usuario_id' not in session:
        flash('Por favor, faça login para continuar.', 'error')
        return redirect(url_for('login'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Seleciona todas as entradas (pix, cartão, cédula) do usuário logado
        cursor.execute(
            "SELECT id_transacao, tipo_transacao, valor, data_hora, usuario_id, descricao, banco_pagamento, forma_pagamento, dono_transacao "
            "FROM transacoes "
            "WHERE tipo_transacao IN ('pix', 'cartao', 'cedula') AND usuario_id = ? "
            "ORDER BY data_hora DESC",
            (session['usuario_id'],)
        )
        entradas = cursor.fetchall()

        # Seleciona todas as saídas do usuário logado
        cursor.execute(
            "SELECT id_transacao, tipo_transacao, valor, data_hora, usuario_id, descricao, banco_pagamento, forma_pagamento, dono_transacao "
            "FROM transacoes "
            "WHERE tipo_transacao = 'saida' AND usuario_id = ? "
            "ORDER BY data_hora DESC",
            (session['usuario_id'],)
        )
        saidas = cursor.fetchall()

        return render_template('ver_transacoes.html', entradas=entradas, saidas=saidas)

    except Exception as e:
        logging.error(f'Erro ao visualizar transações: {str(e)}')
        return render_template('error.html', message=f"Erro ao visualizar transações: {str(e)}"), 500
    finally:
        cursor.close()
        conn.close()        

# Rota para deletar uma transação
# Rota para deletar uma transação
@app.route('/deletar_transacao', methods=['POST'])
def deletar_transacao():
    if 'usuario_id' not in session:
        return jsonify({'success': False, 'message': 'Usuário não logado.'}), 401

    try:
        transacao_id = request.form.get('transacao_id')
        if not transacao_id:
            return jsonify({'success': False, 'message': 'ID da transação não fornecido.'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT usuario_id FROM transacoes WHERE id_transacao = ?", (transacao_id,))
        result = cursor.fetchone()
        if not result or result[0] != session['usuario_id']:
            return jsonify({'success': False, 'message': 'Transação não encontrada ou não autorizada.'}), 403

        cursor.execute("DELETE FROM transacoes WHERE id_transacao = ?", (transacao_id,))
        conn.commit()

        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# Rota para a página de saídas
# Rota para a página de saídas
@app.route('/saida', methods=['GET', 'POST'])
def saida():
    if 'usuario_id' not in session:
        flash('Por favor, faça login para continuar.', 'error')
        return redirect(url_for('login'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if request.method == 'POST':
            valor = float(request.form['valor'])
            if valor <= 0:
                flash('O valor da saída deve ser maior que zero.', 'error')
                return redirect(url_for('saida'))
            descricao = request.form.get('descricao', '')
            banco_pagamento = request.form.get('banco_pagamento')
            forma_pagamento = request.form.get('forma_pagamento')
            dono_banco = request.form.get('dono_banco')

            cursor.execute(
                "INSERT INTO transacoes (tipo_transacao, valor, data_hora, usuario_id, descricao, banco_pagamento, forma_pagamento, dono_transacao) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ('saida', -valor, datetime.now(), session['usuario_id'], descricao, banco_pagamento, forma_pagamento, dono_banco)
            )
            conn.commit()
            flash('Saída registrada com sucesso!', 'success')
            return redirect(url_for('saida'))

        cursor.execute("SELECT data_hora, valor, descricao, banco_pagamento, forma_pagamento, dono_transacao, id_transacao FROM transacoes WHERE tipo_transacao = 'saida' AND usuario_id = ? ORDER BY data_hora DESC", session['usuario_id'])
        saidas = cursor.fetchall()
        return render_template('saida.html', saidas=saidas, current_datetime=get_current_datetime())

    except Exception as e:
        logging.error(f'Erro ao processar saída: {str(e)}')
        return render_template('error.html', message=f"Erro ao processar saída: {str(e)}"), 500
    finally:
        cursor.close()
        conn.close()

# Rota para deletar uma transação (específica para saídas)
@app.route('/deletar_transacao_saida', methods=['POST'])
def deletar_transacao_saida():
    if 'usuario_id' not in session:
        return jsonify({'success': False, 'message': 'Usuário não logado.'}), 401

    try:
        transacao_id = request.form.get('transacao_id')
        if not transacao_id:
            return jsonify({'success': False, 'message': 'ID da transação não fornecido.'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT usuario_id FROM transacoes WHERE id_transacao = ?", (transacao_id,))
        result = cursor.fetchone()
        if not result or result[0] != session['usuario_id']:
            return jsonify({'success': False, 'message': 'Transação não encontrada ou não autorizada.'}), 403

        cursor.execute("DELETE FROM transacoes WHERE id_transacao = ?", (transacao_id,))
        conn.commit()

        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()



        
# Rota para a página de análise financeira
@app.route('/analise', methods=['GET', 'POST'])
def analise():
    if 'usuario_id' not in session:
        flash('Por favor, faça login para continuar.', 'error')
        return redirect(url_for('login'))

    entradas = 0
    saidas = 0
    saldo = 0
    transacoes_detalhadas = []
    total_entrada_mes = 0
    total_saida_mes = 0
    mes_relatorio = ""
    data_inicio = None
    data_fim = None
    current_datetime = get_current_datetime()
    # Lista de dias da semana em português
    dias_semana = ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo']

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if request.method == 'POST':
            if 'analisar' in request.form:
                data_inicio_str = request.form.get('data_inicio')
                data_fim_str = request.form.get('data_fim')

                data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d')
                data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d') + timedelta(days=1) - timedelta(seconds=1)

                session['data_inicio'] = data_inicio_str
                session['data_fim'] = data_fim_str

                cursor.execute(
                    "SELECT tipo_transacao, valor, data_hora, banco_pagamento, dono_transacao FROM transacoes WHERE data_hora BETWEEN ? AND ? AND usuario_id = ?",
                    (data_inicio, data_fim, session['usuario_id'])
                )
                transacoes = cursor.fetchall()

                entradas = sum(t[1] for t in transacoes if t[0] != 'saida')
                saidas = sum(abs(t[1]) for t in transacoes if t[0] == 'saida')
                saldo = entradas - saidas

                for transacao in transacoes:
                    data = transacao[2].strftime('%d/%m/%Y %H:%M')
                    dia_semana = dias_semana[transacao[2].weekday()]  # Usa a lista em português
                    pix = transacao[1] if transacao[0] == 'pix' else 0
                    dinheiro = transacao[1] if transacao[0] == 'cedula' else 0
                    cartao = transacao[1] if transacao[0] == 'cartao' else 0
                    saida = abs(transacao[1]) if transacao[0] == 'saida' else 0
                    total_entrada = pix + dinheiro + cartao
                    total_saida = saida
                    transacoes_detalhadas.append({
                        'data': data,
                        'dia_semana': dia_semana,
                        'pix': pix,
                        'dinheiro': dinheiro,
                        'cartao': cartao,
                        'saidas': saida,
                        'total_entrada': total_entrada,
                        'total_saida': total_saida,
                        'dono_transacao': transacao[4]
                    })

            else:
                filtro = request.form['filtro']
                data_filtro = request.form['data']

                if filtro == 'dia':
                    cursor.execute(
                        "SELECT tipo_transacao, valor, data_hora, banco_pagamento, dono_transacao FROM transacoes WHERE CAST(data_hora AS DATE) = ? AND usuario_id = ?",
                        (data_filtro, session['usuario_id'])
                    )
                    transacoes = cursor.fetchall()
                    entradas = sum(t[1] for t in transacoes if t[0] != 'saida')
                    saidas = sum(abs(t[1]) for t in transacoes if t[0] == 'saida')
                    saldo = entradas - saidas

                    for transacao in transacoes:
                        data = transacao[2].strftime('%d/%m/%Y %H:%M')
                        dia_semana = dias_semana[transacao[2].weekday()]  # Usa a lista em português
                        pix = transacao[1] if transacao[0] == 'pix' else 0
                        dinheiro = transacao[1] if transacao[0] == 'cedula' else 0
                        cartao = transacao[1] if transacao[0] == 'cartao' else 0
                        saida = abs(transacao[1]) if transacao[0] == 'saida' else 0
                        total_entrada = pix + dinheiro + cartao
                        total_saida = saida
                        transacoes_detalhadas.append({
                            'data': data,
                            'dia_semana': dia_semana,
                            'pix': pix,
                            'dinheiro': dinheiro,
                            'cartao': cartao,
                            'saidas': saida,
                            'total_entrada': total_entrada,
                            'total_saida': total_saida,
                            'dono_transacao': transacao[4]
                        })

                    mes = data_filtro[:7]
                    cursor.execute(
                        "SELECT tipo_transacao, valor FROM transacoes WHERE YEAR(data_hora) = ? AND MONTH(data_hora) = ? AND usuario_id = ?",
                        (mes[:4], mes[5:7], session['usuario_id'])
                    )
                    transacoes_mes = cursor.fetchall()
                    total_entrada_mes = sum(t[1] for t in transacoes_mes if t[0] != 'saida')
                    total_saida_mes = sum(abs(t[1]) for t in transacoes_mes if t[0] == 'saida')
                    mes_relatorio = f"{calendar.month_name[int(mes[5:7])]} {mes[:4]}"

                else:
                    cursor.execute(
                        "SELECT tipo_transacao, valor, data_hora, banco_pagamento, dono_transacao FROM transacoes WHERE YEAR(data_hora) = ? AND MONTH(data_hora) = ? AND usuario_id = ?",
                        (data_filtro[:4], data_filtro[5:7], session['usuario_id'])
                    )
                    transacoes = cursor.fetchall()
                    entradas = sum(t[1] for t in transacoes if t[0] != 'saida')
                    saidas = sum(abs(t[1]) for t in transacoes if t[0] == 'saida')
                    saldo = entradas - saidas

                    transacoes_por_dia = {}
                    for transacao in transacoes:
                        data = transacao[2].strftime('%Y-%m-%d')
                        if data not in transacoes_por_dia:
                            transacoes_por_dia[data] = {'pix': 0, 'dinheiro': 0, 'cartao': 0, 'saidas': 0, 'dono_transacao': transacao[4]}
                        if transacao[0] == 'pix':
                            transacoes_por_dia[data]['pix'] += transacao[1]
                        elif transacao[0] == 'cedula':
                            transacoes_por_dia[data]['dinheiro'] += transacao[1]
                        elif transacao[0] == 'cartao':
                            transacoes_por_dia[data]['cartao'] += transacao[1]
                        elif transacao[0] == 'saida':
                            transacoes_por_dia[data]['saidas'] += abs(transacao[1])

                    for data, valores in transacoes_por_dia.items():
                        dia_semana = dias_semana[datetime.strptime(data, '%Y-%m-%d').weekday()]  # Usa a lista em português
                        total_entrada = valores['pix'] + valores['dinheiro'] + valores['cartao']
                        total_saida = valores['saidas']
                        transacoes_detalhadas.append({
                            'data': data,
                            'dia_semana': dia_semana,
                            'pix': valores['pix'],
                            'dinheiro': valores['dinheiro'],
                            'cartao': valores['cartao'],
                            'saidas': valores['saidas'],
                            'total_entrada': total_entrada,
                            'total_saida': total_saida,
                            'dono_transacao': valores['dono_transacao']
                        })
                    total_entrada_mes = entradas
                    total_saida_mes = saidas
                    mes_relatorio = f"{calendar.month_name[int(data_filtro[5:7])]} {data_filtro[:4]}"

    except Exception as e:
        logging.error(f'Erro ao processar análise: {str(e)}')
        return render_template('error.html', message=f"Erro ao processar análise: {str(e)}"), 500
    finally:
        cursor.close()
        conn.close()

    return render_template('analise.html', entradas=entradas, saidas=saidas, saldo=saldo, transacoes_detalhadas=transacoes_detalhadas, total_entrada_mes=total_entrada_mes, total_saida_mes=total_saida_mes, mes_relatorio=mes_relatorio, current_datetime=current_datetime, data_inicio=data_inicio, data_fim=data_fim)

# Rota para exportar os dados da análise em formato CSV
@app.route('/exportar_csv', methods=['POST'])
def exportar_csv():
    if 'usuario_id' not in session:
        flash('Por favor, faça login para continuar.', 'error')
        return redirect(url_for('login'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        data_inicio_str = session.get('data_inicio')
        data_fim_str = session.get('data_fim')

        transacoes = []
        if data_inicio_str and data_fim_str:
            data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d')
            data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d') + timedelta(days=1) - timedelta(seconds=1)

            cursor.execute(
                "SELECT tipo_transacao, valor, data_hora, banco_pagamento, dono_transacao FROM transacoes WHERE data_hora BETWEEN ? AND ? AND usuario_id = ?",
                (data_inicio, data_fim, session['usuario_id'])
            )
            transacoes = cursor.fetchall()
        else:
            flash('Nenhum período selecionado para exportação.', 'error')
            return redirect(url_for('analise'))

        si = StringIO()
        writer = csv.writer(si)
        writer.writerow(['Data', 'Dia da Semana', 'Pix', 'Dinheiro', 'Cartao', 'Saidas', 'Total Entrada', 'Total Saida', 'Dono Transacao'])

        # Lista de dias da semana em português
        dias_semana = ['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo']
        
        for transacao in transacoes:
            data = transacao[2].strftime('%d/%m/%Y %H:%M')
            dia_semana = dias_semana[transacao[2].weekday()]  # Usa a lista em português
            pix = transacao[1] if transacao[0] == 'pix' else 0
            dinheiro = transacao[1] if transacao[0] == 'cedula' else 0
            cartao = transacao[1] if transacao[0] == 'cartao' else 0
            saida = abs(transacao[1]) if transacao[0] == 'saida' else 0
            total_entrada = pix + dinheiro + cartao
            total_saida = saida
            writer.writerow([
                data,
                dia_semana,
                pix,
                dinheiro,
                cartao,
                saida,
                total_entrada,
                total_saida,
                transacao[4]
            ])

        output = si.getvalue()
        si.close()
        return Response(
            output,
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=analise_financeira.csv'}
        )

    except Exception as e:
        logging.error(f'Erro ao exportar CSV: {str(e)}')
        return render_template('error.html', message=f"Erro ao exportar CSV: {str(e)}"), 500
    finally:
        cursor.close()
        conn.close()

# Rota para a página de dashboard
@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    # Verifica se o usuário está logado; redireciona para login se não estiver
    if 'usuario_id' not in session:
        flash('Por favor, faça login para continuar.', 'error')
        return redirect(url_for('login'))

    try:
        conn = get_db_connection()  # Estabelece conexão com o banco de dados
        cursor = conn.cursor()

        # Inicializa variáveis com valores padrão para evitar erros de serialização
        total_entradas = 0.0
        total_saidas = 0.0
        periodo_label = "Selecione um período para análise"
        dados_vela = []  # Lista para dados do gráfico de linha (evolução do saldo)
        dados_pizza = {'pix': 0.0, 'cartao': 0.0, 'cedula': 0.0, 'saida': 0.0}  # Dicionário para dados do gráfico de pizza

        if request.method == 'POST':
            # Obtém as datas do formulário
            data_inicio_str = request.form.get('data_inicio')
            data_fim_str = request.form.get('data_fim')

            try:
                # Converte as strings para objetos datetime
                data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d')
                data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d')

                # Ajusta para incluir o dia inteiro
                data_inicio = data_inicio.replace(hour=0, minute=0, second=0)
                data_fim = data_fim.replace(hour=23, minute=59, second=59)
            except ValueError as ve:
                # Exibe mensagem de erro se as datas forem inválidas
                flash('Datas inválidas. Use o formato AAAA-MM-DD.', 'error')
                logging.error(f"Erro ao converter datas: {str(ve)}")
                return redirect(url_for('dashboard'))

            # Log para depuração
            logging.info(f"Período selecionado: {data_inicio} até {data_fim}")

            # Executa a consulta SQL, passando objetos datetime diretamente
            cursor.execute(
                """
                SELECT
                    data,
                    SUM(CASE WHEN tipo_movimento = 'entrada' THEN valor ELSE 0 END) AS total_entrada,
                    SUM(CASE WHEN tipo_movimento = 'saida' THEN valor ELSE 0 END) AS total_saida
                FROM (
                    SELECT
                        CAST(data_hora AS DATE) AS data,
                        CASE 
                            WHEN tipo_transacao = 'saida' THEN 'saida'
                            ELSE 'entrada'
                        END AS tipo_movimento,
                        valor
                    FROM transacoes
                    WHERE data_hora BETWEEN ? AND ? AND usuario_id = ?
                ) AS t
                GROUP BY data
                ORDER BY data
                """,
                (data_inicio, data_fim, session['usuario_id'])
            )
            transacoes_por_dia = cursor.fetchall()
            periodo_label = f"{data_inicio.strftime('%Y-%m-%d')} a {data_fim.strftime('%Y-%m-%d')}"

            # Calcula totais gerais e prepara dados para o gráfico de linha
            saldo_acumulado = 0.0
            for row in transacoes_por_dia:
                data = row[0].strftime('%Y-%m-%d')  # Formata a data
                entradas = float(row[1]) if row[1] else 0.0  # Total de entradas do dia
                saidas = float(abs(row[2])) if row[2] else 0.0  # Total de saídas do dia (valor absoluto)
                saldo_acumulado += (entradas - saidas)  # Atualiza o saldo acumulado
                dados_vela.append({'x': data, 'c': round(saldo_acumulado, 2)})  # Adiciona ao gráfico de linha

            # Calcula totais gerais de entradas e saídas
            total_entradas = sum(float(row[1]) if row[1] else 0.0 for row in transacoes_por_dia)
            total_saidas = sum(float(abs(row[2])) if row[2] else 0.0 for row in transacoes_por_dia)

            # Consulta para dados do gráfico de pizza (total por tipo de transação no período)
            cursor.execute(
                """
                SELECT tipo_transacao, SUM(valor) AS total
                FROM transacoes
                WHERE data_hora BETWEEN ? AND ? AND usuario_id = ?
                GROUP BY tipo_transacao
                """,
                (data_inicio, data_fim, session['usuario_id'])
            )
            transacoes = cursor.fetchall()
            for t in transacoes:
                tipo = t[0]
                valor = float(t[1])
                if tipo == 'pix':
                    dados_pizza['pix'] += valor
                elif tipo == 'cartao':
                    dados_pizza['cartao'] += valor
                elif tipo == 'cedula':
                    dados_pizza['cedula'] += valor
                elif tipo == 'saida':
                    dados_pizza['saida'] += abs(valor)

        # Renderiza o template com os dados calculados
        return render_template(
            'dashboard.html',
            total_entradas=total_entradas,
            total_saidas=total_saidas,
            periodo_label=periodo_label,
            dados_vela=dados_vela,
            dados_pizza=dados_pizza,
            current_datetime=get_current_datetime()
        )

    except Exception as e:
        # Registra erro no log e retorna uma resposta simples, já que error.html não existe
        logging.error(f'Erro ao processar dashboard: {str(e)}')
        return f"Erro ao processar dashboard: {str(e)}", 500
    finally:
        # Fecha cursor e conexão para liberar recursos
        cursor.close()
        conn.close()
# Rota para logout
@app.route('/logout')
def logout():
    session.pop('usuario_id', None)
    session.pop('data_inicio', None)
    session.pop('data_fim', None)
    session.pop('redirect_count', None)  # Remove o contador de redirecionamentos
    flash('Você saiu com sucesso!', 'success')
    return redirect(url_for('login'))

# Função para encerrar o servidor corretamente
def shutdown_server():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is not None:
        func()
    logging.info("Encerrando o servidor Flask...")
    sys.exit(0)

# Manipulador de sinal para CTRL+C
def signal_handler(sig, frame):
    logging.info('Você pressionou Ctrl+C!')
    shutdown_server()


@app.route('/anotacoes', methods=['GET', 'POST'])
def anotacoes():
    if 'usuario_id' not in session:
        flash('Por favor, faça login para continuar.', 'error')
        return redirect(url_for('login'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Ação para excluir um lembrete
        if request.method == 'POST' and 'delete_id' in request.form:
            delete_id = request.form['delete_id']
            cursor.execute("DELETE FROM anotacoes WHERE id = ? AND usuario_id = ?", (delete_id, session['usuario_id']))
            conn.commit()
            flash('Lembrete excluído com sucesso!', 'success')
            return redirect(url_for('anotacoes'))

        # Ação para criar um novo lembrete
        if request.method == 'POST':
            nome_lembrete = request.form['nome_lembrete']
            data_criacao = request.form['data_criacao']
            data_lembrete = request.form['data_lembrete']
            hora_alarme = request.form['hora_alarme']
            descricao = request.form['descricao']

            # Validações básicas
            if not nome_lembrete or not data_criacao or not data_lembrete or not hora_alarme or not descricao:
                flash('Todos os campos são obrigatórios.', 'error')
                return redirect(url_for('anotacoes'))

            try:
                cursor.execute(
                    "INSERT INTO anotacoes (nome_lembrete, data_criacao, data_lembrete, hora_alarme, descricao, usuario_id) VALUES (?, ?, ?, ?, ?, ?)",
                    (nome_lembrete, data_criacao, data_lembrete, hora_alarme, descricao, session['usuario_id'])
                )
                conn.commit()
                flash('Lembrete criado com sucesso!', 'success')
            except Exception as e:
                logging.error(f'Erro ao criar lembrete: {str(e)}')
                flash('Erro ao criar lembrete.', 'error')

            return redirect(url_for('anotacoes'))

        # Listar lembretes ordenados por data de criação (mais recente primeiro)
        cursor.execute(
            "SELECT id, nome_lembrete, data_criacao, data_lembrete, hora_alarme, descricao FROM anotacoes WHERE usuario_id = ? ORDER BY data_criacao DESC",
            (session['usuario_id'],)
        )
        lembretes = cursor.fetchall()

        return render_template(
            'anotacoes.html',
            lembretes=lembretes,
            current_datetime=get_current_datetime()
        )

    except Exception as e:
        logging.error(f'Erro ao processar anotações: {str(e)}')
        return render_template('error.html', message=f"Erro ao processar anotações: {str(e)}"), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/contas_a_pagar', methods=['GET', 'POST'])
def contas_a_pagar():
    if 'usuario_id' not in session:
        flash('Por favor, faça login para continuar.', 'error')
        return redirect(url_for('login'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Ação para excluir uma conta
        if request.method == 'POST' and 'delete_id' in request.form:
            delete_id = request.form['delete_id']
            cursor.execute("DELETE FROM contas_a_pagar WHERE id = ? AND usuario_id = ?", (delete_id, session['usuario_id']))
            conn.commit()
            flash('Conta excluída com sucesso!', 'success')
            return redirect(url_for('contas_a_pagar'))

        # Ação para atualizar o status de uma conta
        if request.method == 'POST' and 'update_status' in request.form:
            conta_id = request.form['conta_id']
            novo_status = request.form['status']
            cursor.execute(
                "UPDATE contas_a_pagar SET status = ? WHERE id = ? AND usuario_id = ?",
                (novo_status, conta_id, session['usuario_id'])
            )
            conn.commit()
            flash('Status da conta atualizado com sucesso!', 'success')
            return redirect(url_for('contas_a_pagar'))

        # Ação para criar uma nova conta
        if request.method == 'POST' and 'nome_conta' in request.form:
            nome_conta = request.form['nome_conta']
            descricao = request.form['descricao']
            hora_alarme = request.form['hora_alarme']
            data_vencimento = request.form['data_vencimento']
            valor = float(request.form['valor'])

            # Validações básicas
            if not nome_conta or not descricao or not hora_alarme or not data_vencimento or valor <= 0:
                flash('Todos os campos são obrigatórios e o valor deve ser maior que zero.', 'error')
                return redirect(url_for('contas_a_pagar'))

            # Verificar se a data de vencimento já passou
            data_vencimento_dt = datetime.strptime(data_vencimento, '%Y-%m-%d').date()
            hoje = date.today()
            status = 'vencida' if data_vencimento_dt < hoje else 'a_pagar'

            try:
                cursor.execute(
                    "INSERT INTO contas_a_pagar (nome_conta, descricao, hora_alarme, data_vencimento, valor, status, usuario_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (nome_conta, descricao, hora_alarme, data_vencimento, valor, status, session['usuario_id'])
                )
                conn.commit()
                flash('Conta criada com sucesso!', 'success')
            except Exception as e:
                logging.error(f'Erro ao criar conta: {str(e)}')
                flash('Erro ao criar conta.', 'error')

            return redirect(url_for('contas_a_pagar'))

        # Listar contas ordenadas por data de vencimento (mais próxima primeiro)
        cursor.execute(
            "SELECT id, nome_conta, descricao, hora_alarme, data_vencimento, valor, status FROM contas_a_pagar WHERE usuario_id = ? ORDER BY data_vencimento ASC",
            (session['usuario_id'],)
        )
        contas = cursor.fetchall()

        # Atualizar status de contas vencidas
        hoje = date.today()
        for conta in contas:
            data_vencimento = datetime.strptime(str(conta[4]), '%Y-%m-%d').date()
            if data_vencimento < hoje and conta[6] not in ['pago', 'vencida']:
                cursor.execute(
                    "UPDATE contas_a_pagar SET status = 'vencida' WHERE id = ? AND usuario_id = ?",
                    (conta[0], session['usuario_id'])
                )
                conn.commit()

        # Recarregar contas após atualização de status
        cursor.execute(
            "SELECT id, nome_conta, descricao, hora_alarme, data_vencimento, valor, status FROM contas_a_pagar WHERE usuario_id = ? ORDER BY data_vencimento ASC",
            (session['usuario_id'],)
        )
        contas = cursor.fetchall()

        return render_template(
            'contas_a_pagar.html',
            contas=contas,
            current_datetime=get_current_datetime()
        )

    except Exception as e:
        logging.error(f'Erro ao processar contas a pagar: {str(e)}')
        return render_template('error.html', message=f"Erro ao processar contas a pagar: {str(e)}"), 500
    finally:
        cursor.close()
        conn.close()    

# Bloco principal para iniciar o servidor Flask
if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)  # Registra o manipulador de sinal para CTRL+C
    print("Iniciando o servidor Flask...")
    port = 5000
    max_attempts = 5
    attempt = 0

    while attempt < max_attempts:
        if is_port_in_use(port):
            print(f"Porta {port} está em uso. Tentando a próxima porta...")
            port += 1
            attempt += 1
        else:
            try:
                # Configura a reutilização de portas
                socket.setdefaulttimeout(1)
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    app.run(debug=True, host='0.0.0.0', port=port, use_reloader=False)  # Desativa o reloader automático
                break
            except Exception as e:
                print(f"Erro ao iniciar o servidor na porta {port}: {e}")
                port += 1
                attempt += 1

    if attempt == max_attempts:
        print(f"Não foi possível encontrar uma porta livre após {max_attempts} tentativas. Encerrando...")
        exit(1)
