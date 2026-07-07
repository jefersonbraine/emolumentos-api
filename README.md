<div align="center">
  <img src="assets/imgs/Banner - emolumentos-api.png" alt="Emolumentos API Banner" width="1920" />

</div>

API HTTP para cálculo de emolumentos de cartório do Paraná. É uma casca fina
sobre a biblioteca [`emolumentos-pr`](https://pypi.org/project/emolumentos-pr/)
(instalada do PyPI): toda a regra de negócio mora na lib; a API só recebe o
pedido, calcula e devolve JSON. Feita para servir um front-end (ex.: Angular).

## Rodar localmente

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

A API sobe em `http://127.0.0.1:8000`. Documentação interativa automática em
`http://127.0.0.1:8000/docs`.

## Endpoints

| Método | Rota         | O que faz                                   |
|--------|--------------|---------------------------------------------|
| GET    | `/health`    | Health check (`{"status": "ok"}`)           |
| GET    | `/tipos`     | Lista os tipos de ato suportados            |
| POST   | `/calcular`  | Calcula o emolumento e devolve o breakdown  |

### POST /calcular

Corpo:

```json
{
  "tipo": "compra_e_venda",
  "valores": ["250.000,00"],
  "usufruto": false,
  "partes_adicionais": 0
}
```

- `tipo`: `compra_e_venda`, `doacao`, `sem_valor` ou `procuracao`.
- `valores`: lista de valores dos imóveis. Aceita formato brasileiro
  (`"250.000,00"`) e internacional (`"250000"`). Vazio para atos sem valor.
- `usufruto`: só relevante em doação (dobra o Funrejus).
- `partes_adicionais`: só relevante em procuração.

Resposta (200):

```json
{
  "tipo": "compra_e_venda",
  "componentes": [
    {"nome": "Emolumentos", "valor": "1377.24", "valor_brl": "R$ 1.377,24"},
    ...
  ],
  "total": "2043.414",
  "total_brl": "R$ 2.043,41"
}
```

Valores monetários vêm como **string** (preservam a precisão do `Decimal`), com
a versão formatada em R$ ao lado. Entradas inválidas retornam `400` com a
mensagem no campo `detail`.

## Docker

```bash
docker build -t emolumentos-api .
docker run -p 8000:8000 emolumentos-api
```

## Testes

```bash
pip install pytest httpx
pytest
```

## Notas de produção

- **CORS:** hoje liberado para qualquer origem (`allow_origins=["*"]`). Em
  produção, troque pelo domínio do front-end.
- **HTTPS:** o navegador bloqueia um site HTTPS chamando uma API HTTP. Ponha a
  API atrás de um proxy com TLS (ex.: Caddy/Nginx) ou um domínio com certificado.
