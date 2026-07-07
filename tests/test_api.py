"""Testes da API com autenticação e rate limiting."""

import os

import pytest
from fastapi.testclient import TestClient

# Define a API_KEY antes de importar o app, pra ter chave fixa nos testes.
os.environ["API_KEY"] = "chave-de-teste-123"

from app.main import app  # noqa: E402

client = TestClient(app)
HEADERS = {"X-API-Key": "chave-de-teste-123"}
HEADERS_ERRADO = {"X-API-Key": "chave-errada"}


# --- Rotas públicas --------------------------------------------------------
def test_health_sem_chave():
    """Health check é público — sem chave, sem problema."""
    assert client.get("/health").json() == {"status": "ok"}


def test_docs_publico():
    """/docs é público."""
    assert client.get("/docs").status_code == 200


# --- Autenticação ----------------------------------------------------------
def test_tipos_sem_chave_retorna_401():
    assert client.get("/tipos").status_code == 401


def test_calcular_sem_chave_retorna_401():
    r = client.post("/calcular", json={"tipo": "compra_e_venda", "valores": ["50000"]})
    assert r.status_code == 401


def test_tipos_com_chave_errada_retorna_401():
    assert client.get("/tipos", headers=HEADERS_ERRADO).status_code == 401


def test_calcular_com_chave_errada_retorna_401():
    r = client.post(
        "/calcular",
        json={"tipo": "compra_e_venda", "valores": ["50000"]},
        headers=HEADERS_ERRADO,
    )
    assert r.status_code == 401


# --- Rotas protegidas com chave correta ------------------------------------
def test_tipos_lista_os_quatro_atos():
    valores = [t["valor"] for t in client.get("/tipos", headers=HEADERS).json()["tipos"]]
    assert set(valores) == {"compra_e_venda", "doacao", "sem_valor", "procuracao"}


def test_calcular_compra_e_venda_formato_brasileiro():
    r = client.post(
        "/calcular",
        json={"tipo": "compra_e_venda", "valores": ["250.000,00"]},
        headers=HEADERS,
    )
    assert r.status_code == 200
    dados = r.json()
    assert dados["total"] == "2043.414"
    assert dados["total_brl"] == "R$ 2.043,41"


def test_calcular_multiobjeto():
    r = client.post(
        "/calcular",
        json={"tipo": "compra_e_venda", "valores": ["50000", "30000"]},
        headers=HEADERS,
    )
    assert r.json()["total"] == "2238.545"


def test_calcular_sem_valor():
    r = client.post("/calcular", json={"tipo": "sem_valor"}, headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["total"] == "264.039"


def test_tipo_invalido_retorna_400():
    r = client.post(
        "/calcular",
        json={"tipo": "inexistente", "valores": ["1000"]},
        headers=HEADERS,
    )
    assert r.status_code == 400


def test_valor_invalido_retorna_400():
    r = client.post(
        "/calcular",
        json={"tipo": "compra_e_venda", "valores": ["abc"]},
        headers=HEADERS,
    )
    assert r.status_code == 400
    assert "inválido" in r.json()["detail"].lower()


def test_ato_com_valor_sem_valores_retorna_400():
    r = client.post(
        "/calcular",
        json={"tipo": "compra_e_venda", "valores": []},
        headers=HEADERS,
    )
    assert r.status_code == 400
