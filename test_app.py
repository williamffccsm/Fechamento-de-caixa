# Importando as bibliotecas
import sys
import os

from traitlets import Any
sys.path.append(os.path.dirname(os.path.abspath(__file__)))  # Adiciona o diretório atual ao caminho
import pytest 
from app import app, get_db_connection, USUARIO_VALIDO, initialize_database
import pyodbc
from flask import session
from datetime import datetime

import pytest
from datetime import datetime

# Fixture para o cliente de teste
@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False  # Desativa CSRF para testes
    with app.test_client() as client:
        with app.app_context():
            initialize_database()  # Inicializa o banco de dados
            yield client
# Comentário: Esta fixture configura o ambiente de teste, inicializando o Flask em modo de teste e desativando CSRF para simplificar requisições HTTP simuladas. É usada por todos os testes que interagem com a aplicação web, fornecendo um cliente de teste para simular requisições.

# Teste 1: Login com credenciais corretas
def test_login_success(client):
    # Tipo de Teste: UNITÁRIO
    # Comentário: Teste unitário que verifica o comportamento isolado do endpoint de login ('/'). Testa se credenciais válidas ('USUARIO_VALIDO', '123') resultam em uma resposta HTTP 200, mensagem de sucesso e definição correta do 'usuario_id' na sessão. Foca apenas na funcionalidade de autenticação, sem dependências externas além do cliente de teste.
    response = client.post('/', data={'login': USUARIO_VALIDO, 'senha': '123'}, follow_redirects=True)
    if response.status_code == 200 and 'Login bem-sucedido!' in response.get_data(as_text=True):
        assert session.get('usuario_id') == 1
        print("Teste 1 - Login com credenciais corretas: SUCESSO")
    else:
        pytest.fail(f"Teste 1 - Login com credenciais corretas: FALHA - Status: {response.status_code}, Resposta: {response.get_data(as_text=True)}")

# Teste 2: Login com usuário errado
def test_login_wrong_user(client):
    # Tipo de Teste: UNITÁRIO
    # Comentário: Teste unitário que verifica o comportamento do endpoint de login ('/') quando um usuário inválido é fornecido. Confirma que a resposta HTTP é 200, exibe a mensagem de erro 'Credenciais inválidas' e não define 'usuario_id' na sessão. Testa isoladamente a validação de credenciais.
    response = client.post('/', data={'login': 'wrong_user', 'senha': '123'}, follow_redirects=True)
    if response.status_code == 200 and 'Credenciais inválidas. Tente novamente.' in response.get_data(as_text=True):
        assert session.get('usuario_id') is None
        print("Teste 2 - Login com usuário errado: SUCESSO (falha esperada)")
    else:
        pytest.fail(f"Teste 2 - Login com usuário errado: FALHA - Status: {response.status_code}, Resposta: {response.get_data(as_text=True)}")

# Teste 3: Login com senha errada
def test_login_wrong_password(client):
    # Tipo de Teste: UNITÁRIO
    # Comentário: Teste unitário similar ao teste 2, mas verifica o comportamento do endpoint de login ('/') com uma senha incorreta. Garante que a resposta HTTP é 200, exibe a mensagem de erro 'Credenciais inválidas' e não define 'usuario_id'. Foca na validação isolada da senha.
    response = client.post('/', data={'login': USUARIO_VALIDO, 'senha': 'wrong_password'}, follow_redirects=True)
    if response.status_code == 200 and 'Credenciais inválidas. Tente novamente.' in response.get_data(as_text=True):
        assert session.get('usuario_id') is None
        print("Teste 3 - Login com senha errada: SUCESSO (falha esperada)")
    else:
        pytest.fail(f"Teste 3 - Login com senha errada: FALHA - Status: {response.status_code}, Resposta: {response.get_data(as_text=True)}")

# Teste 4: Conexão com o banco de dados
def test_database_connection():
    # Tipo de Teste: UNITÁRIO
    # Comentário: Teste unitário que verifica a funcionalidade isolada da conexão com o banco de dados usando 'get_db_connection'. Executa uma consulta simples ('SELECT 1') para confirmar que a conexão é estabelecida e funciona corretamente. Não depende da aplicação Flask, apenas da biblioteca pyodbc.
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        if result and result[0] == 1:
            print("Teste 4 - Conexão com o banco de dados: SUCESSO")
        else:
            pytest.fail("Teste 4 - Conexão com o banco de dados: FALHA - Resultado inesperado do SELECT 1")
        conn.close()
    except pyodbc.Error as e:
        pytest.fail(f"Teste 4 - Conexão com o banco de dados: FALHA - Erro: {e}")

# Teste 5: Registro de entrada com valor válido
def test_entrada_functionality(client):
    # Tipo de Teste: INTEGRAÇÃO
    # Comentário: Teste de integração que verifica a interação entre login, endpoint de entrada ('/entrada') e banco de dados. Após fazer login, registra uma transação PIX válida (100.00) e confirma que ela é salva no banco com o valor e data corretos. Testa a integração entre autenticação, processamento de transações e persistência de dados.
    client.post('/', data={'login': USUARIO_VALIDO, 'senha': '123'}, follow_redirects=True)
    response = client.post('/entrada', data={
        'tipo': 'pix',
        'valor': '100.00',
        'descricao': 'Teste entrada',
        'banco_pagamento': 'Banco Teste',
        'dono_transacao': 'Teste User'
    }, follow_redirects=True)
    if response.status_code == 200 and 'Entrada registrada com sucesso!' in response.get_data(as_text=True):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT valor, data_hora FROM transacoes WHERE tipo_transacao = 'pix' AND descricao = 'Teste entrada' ORDER BY data_hora DESC")
        result = cursor.fetchone()
        if result and float(result[0]) == 100.00:
            transacao_data = result[1].strftime('%Y-%m-%d')
            assert transacao_data == datetime.now().strftime('%Y-%m-%d'), f"Data da transação ({transacao_data}) não corresponde à data atual ({datetime.now().strftime('%Y-%m-%d')})"
            print("Teste 5 - Registro de entrada com valor válido: SUCESSO")
        else:
            pytest.fail("Teste 5 - Registro de entrada com valor válido: FALHA - Transação não encontrada ou valor incorreto")
        conn.close()
    else:
        pytest.fail(f"Teste 5 - Registro de entrada com valor válido: FALHA - Status: {response.status_code}, Resposta: {response.get_data(as_text=True)}")

# Teste 6: Registro de entrada com valor inválido (negativo)
def test_entrada_invalid_value(client):
    # Tipo de Teste: INTEGRAÇÃO
    # Comentário: Teste de integração que verifica a interação entre login, endpoint de entrada ('/entrada') e banco de dados ao tentar registrar uma transação PIX com valor inválido (-100.00). Confirma que a transação é rejeitada (mensagem de erro) e não é salva no banco. Testa a integração de validação de entrada e persistência.
    client.post('/', data={'login': USUARIO_VALIDO, 'senha': '123'}, follow_redirects=True)
    response = client.post('/entrada', data={
        'tipo': 'pix',
        'valor': '-100.00',
        'descricao': 'Teste entrada inválida',
        'banco_pagamento': 'Banco Teste',
        'dono_transacao': 'Teste User'
    }, follow_redirects=True)
    if response.status_code == 200 and 'O valor da entrada deve ser maior que zero.' in response.get_data(as_text=True):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT valor FROM transacoes WHERE tipo_transacao = 'pix' AND descricao = 'Teste entrada inválida' ORDER BY data_hora DESC")
        result = cursor.fetchone()
        assert result is None, "Transação com valor inválido foi registrada no banco"
        print("Teste 6 - Registro de entrada com valor inválido: SUCESSO (falha esperada)")
        conn.close()
    else:
        pytest.fail(f"Teste 6 - Registro de entrada com valor inválido: FALHA - Status: {response.status_code}, Resposta: {response.get_data(as_text=True)}")

# Teste 7: Registro de saída com valor válido
def test_saida_functionality(client):
    # Tipo de Teste: INTEGRAÇÃO
    # Comentário: Teste de integração que verifica a interação entre login, endpoint de saída ('/saida') e banco de dados. Após login, registra uma saída válida (50.00) e confirma que ela é salva no banco com valor negativo (-50.00) e data correta. Testa a integração entre autenticação, processamento de saídas e persistência.
    client.post('/', data={'login': USUARIO_VALIDO, 'senha': '123'}, follow_redirects=True)
    response = client.post('/saida', data={
        'valor': '50.00',
        'descricao': 'Teste saída',
        'banco_pagamento': 'Banco Teste',
        'forma_pagamento': 'dinheiro',
        'dono_banco': 'Teste User'
    }, follow_redirects=True)
    if response.status_code == 200 and 'Saída registrada com sucesso!' in response.get_data(as_text=True):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT valor, data_hora FROM transacoes WHERE tipo_transacao = 'saida' AND descricao = 'Teste saída' ORDER BY data_hora DESC")
        result = cursor.fetchone()
        if result and float(result[0]) == -50.00:
            transacao_data = result[1].strftime('%Y-%m-%d')
            assert transacao_data == datetime.now().strftime('%Y-%m-%d'), f"Data da transação ({transacao_data}) não corresponde à data atual ({datetime.now().strftime('%Y-%m-%d')})"
            print("Teste 7 - Registro de saída com valor válido: SUCESSO")
        else:
            pytest.fail("Teste 7 - Registro de saída com valor válido: FALHA - Transação não encontrada ou valor incorreto")
        conn.close()
    else:
        pytest.fail(f"Teste 7 - Registro de saída com valor válido: FALHA - Status: {response.status_code}, Resposta: {response.get_data(as_text=True)}")

# Teste 8: Registro de saída com valor inválido (zero)
def test_saida_zero_value(client):
    # Tipo de Teste: INTEGRAÇÃO
    # Comentário: Teste de integração que verifica a interação entre login, endpoint de saída ('/saida') e banco de dados ao tentar registrar uma saída com valor inválido (0.00). Confirma que a transação é rejeitada (mensagem de erro) e não é salva no banco. Testa a integração de validação de saída e persistência.
    client.post('/', data={'login': USUARIO_VALIDO, 'senha': '123'}, follow_redirects=True)
    response = client.post('/saida', data={
        'valor': '0.00',
        'descricao': 'Teste saída zero',
        'banco_pagamento': 'Banco Teste',
        'forma_pagamento': 'dinheiro',
        'dono_banco': 'Teste User'
    }, follow_redirects=True)
    if response.status_code == 200 and 'O valor da saída deve ser maior que zero.' in response.get_data(as_text=True):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT valor FROM transacoes WHERE tipo_transacao = 'saida' AND descricao = 'Teste saída zero' ORDER BY data_hora DESC")
        result = cursor.fetchone()
        assert result is None, "Transação com valor zero foi registrada no banco"
        print("Teste 8 - Registro de saída com valor zero: SUCESSO (falha esperada)")
        conn.close()
    else:
        pytest.fail(f"Teste 8 - Registro de saída com valor zero: FALHA - Status: {response.status_code}, Resposta: {response.get_data(as_text=True)}")


# Teste 11: Acesso a /ver_transacoes sem login
def test_ver_transacoes_unauthorized(client):
    # Tipo de Teste: UNITÁRIO
    # Coment Ascolta o comportamento isolado do endpoint '/ver_transacoes' quando acessado sem login. Confirma que o acesso é negado, redireciona para a página de login com a mensagem 'Por favor, faça login' e não define 'usuario_id'. Foca na funcionalidade de controle de acesso.
    response = client.get('/ver_transacoes', follow_redirects=True)
    if response.status_code == 200 and 'Por favor, faça login para continuar.' in response.get_data(as_text=True):
        assert session.get('usuario_id') is None
        print("Teste 11 - Acesso a /ver_transacoes sem login: SUCESSO (falha esperada)")
    else:
        pytest.fail(f"Teste 11 - Acesso a /ver_transacoes sem login: FALHA - Status: {response.status_code}, Resposta: {response.get_data(as_text=True)}")

# Teste 12: Logout
def test_logout(client):    
    # Tipo de Teste: UNITÁRIO
    # Comentário: Teste unitário que verifica o comportamento isolado do endpoint de logout ('/logout'). Após login, confirma que o logout limpa a sessão ('usuario_id' é None) e exibe a mensagem 'Você saiu com sucesso!'. Foca apenas na funcionalidade de logout.
    client.post('/', data={'login': USUARIO_VALIDO, 'senha': '123'}, follow_redirects=True)
    response = client.get('/logout', follow_redirects=True)
    if response.status_code == 200 and 'Você saiu com sucesso!' in response.get_data(as_text=True):
        assert session.get('usuario_id') is None
        print("Teste 12 - Logout: SUCESSO")
    else:
        pytest.fail(f"Teste 12 - Logout: FALHA - Status: {response.status_code}, Resposta: {response.get_data(as_text=True)}")
 # Teste 13: Fluxo completo de aceitação



if __name__ == '__main__':
    pytest.main(['-v', __file__])