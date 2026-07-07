"""Testes da API (usam TestClient — não sobem servidor de verdade)."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_tipos_lista_os_quatro_atos():
    valores = [t["valor"] for t in client.get("/tipos").json()["tipos"]]
    assert set(valores) == {"compra_e_venda", "doacao", "sem_valor", "procuracao"}


def test_calcular_compra_e_venda_formato_brasileiro():
    r = client.post("/calcular", json={"tipo": "compra_e_venda", "valores": ["250.000,00"]})
    assert r.status_code == 200
    dados = r.json()
    assert dados["total"] == "2043.414"          # Decimal exato, como string
    assert dados["total_brl"] == "R$ 2.043,41"


def test_calcular_multiobjeto():
    r = client.post("/calcular", json={"tipo": "compra_e_venda", "valores": ["50000", "30000"]})
    assert r.json()["total"] == "2238.545"


def test_calcular_sem_valor_sem_valores():
    r = client.post("/calcular", json={"tipo": "sem_valor"})
    assert r.status_code == 200
    assert r.json()["total"] == "264.039"


def test_tipo_invalido_retorna_400():
    r = client.post("/calcular", json={"tipo": "inexistente", "valores": ["1000"]})
    assert r.status_code == 400


def test_valor_invalido_retorna_400_com_mensagem():
    r = client.post("/calcular", json={"tipo": "compra_e_venda", "valores": ["abc"]})
    assert r.status_code == 400
    assert "inválido" in r.json()["detail"].lower()


def test_ato_com_valor_sem_valor_retorna_400():
    r = client.post("/calcular", json={"tipo": "compra_e_venda", "valores": []})
    assert r.status_code == 400
