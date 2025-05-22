import re
from datetime import datetime
from typing import Any
import pytest
from app import app as flask_app, get_db_connection

USUARIO_VALIDO = 'admin'  # Substitua se necessário

@pytest.fixture
def client():
    flask_app.config['TESTING'] = True
    with flask_app.test_client() as client:
        yield client

def test_aceitacao(client: Any):
    # Limpa transações antigas para ambiente de teste limpo
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transacoes")
    conn.commit()
    conn.close()

    # Passo 1: Login
    response = client.post('/', data={'login': USUARIO_VALIDO, 'senha': '123'}, follow_redirects=True)
    assert response.status_code == 200
    assert 'Login bem-sucedido!' in response.get_data(as_text=True)

    with client.session_transaction() as sess:
        assert sess.get('usuario_id') == 1, "Sessão não iniciada corretamente"
    print("Teste 13 - Login: SUCESSO")

    # Passo 2: Registrar entrada (PIX)
    response = client.post('/entrada', data={
        'tipo': 'pix',
        'valor': '200.00',
        'descricao': 'Teste entrada aceitação',
        'banco_pagamento': 'Banco Teste',
        'dono_transacao': 'Teste User'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert 'Entrada registrada com sucesso!' in response.get_data(as_text=True)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT valor, data_hora 
        FROM transacoes 
        WHERE tipo_transacao = 'pix' 
        AND descricao = 'Teste entrada aceitação' 
        ORDER BY data_hora DESC
    """)
    result = cursor.fetchone()
    conn.close()

    assert result is not None, "Entrada não registrada"
    assert float(result[0]) == 200.00
    assert result[1].strftime('%Y-%m-%d') == datetime.now().strftime('%Y-%m-%d')
    print("Teste 13 - Registro de entrada: SUCESSO")

    # Passo 3: Registrar saída
    response = client.post('/saida', data={
        'valor': '50.00',
        'descricao': 'Teste saída aceitação',
        'banco_pagamento': 'Banco Teste',
        'forma_pagamento': 'dinheiro',
        'dono_banco': 'Teste User excessivo'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert 'Saída registrada com sucesso!' in response.get_data(as_text=True)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT valor, data_hora 
        FROM transacoes 
        WHERE tipo_transacao = 'saida' 
        AND descricao = 'Teste saída aceitação' 
        ORDER BY data_hora DESC
    """)
    result = cursor.fetchone()
    conn.close()

    assert result is not None, "Saída não registrada"
    assert float(result[0]) == -50.00
    assert result[1].strftime('%Y-%m-%d') == datetime.now().strftime('%Y-%m-%d')
    print("Teste 13 - Registro de saída: SUCESSO")

# Execução direta
if __name__ == "__main__":
    flask_app.config['TESTING'] = True
    with flask_app.test_client() as client:
        test_aceitacao(client)
