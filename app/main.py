"""API de cálculo de emolumentos de cartório do Paraná.

Segurança:
- /health e /docs são públicos (monitoramento e documentação).
- /tipos e /calcular exigem API Key no header X-API-Key.
- Rate limiting: 30 requisições/minuto por IP em todas as rotas protegidas.
"""

from __future__ import annotations

import os
import secrets

from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from emolumentos_pr import (
    Ato,
    TipoAto,
    calcular,
    parse_valor,
    resultado_para_dict,
)
from emolumentos_pr.erros import EmolumentoError

# ---------------------------------------------------------------------------
# Configuração: API Key lida da variável de ambiente.
# Em produção, defina API_KEY no ambiente Docker (nunca no código).
# Se a variável não existir, gera uma chave aleatória e imprime no log —
# útil pra primeiro boot, ruim pra produção (muda a cada restart).
# ---------------------------------------------------------------------------
_API_KEY = os.environ.get("API_KEY")
if not _API_KEY:
    _API_KEY = secrets.token_urlsafe(32)
    print(f"[AVISO] API_KEY não definida. Usando chave temporária: {_API_KEY}")
    print("[AVISO] Defina API_KEY como variável de ambiente para produção.")

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def verificar_api_key(key: str | None = Security(API_KEY_HEADER)) -> str:
    """Dependência FastAPI: rejeita requisições sem a chave correta."""
    if not key or not secrets.compare_digest(key, _API_KEY):
        raise HTTPException(status_code=401, detail="API Key inválida ou ausente.")
    return key


# ---------------------------------------------------------------------------
# Rate limiting: 30 req/min por IP.
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="API de Emolumentos PR",
    description=(
        "Cálculo de emolumentos de cartório do Paraná (Tabela XI). "
        "Motor: emolumentos-pr. "
        "Rotas protegidas exigem o header X-API-Key."
    ),
    version="0.2.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS: libera o front-end (Angular) a chamar a API do navegador.
# Em produção, troque ["*"] pelo domínio real do site.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # trocar pelo domínio real do front-end em produção
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------
class PedidoCalculo(BaseModel):
    """Corpo do POST /calcular."""
    tipo: str = Field(..., examples=["compra_e_venda"])
    valores: list[str] = Field(
        default_factory=list,
        description="Valores dos imóveis. Aceita '250.000,00' ou '250000'.",
        examples=[["250.000,00"]],
    )
    usufruto: bool = Field(default=False)
    partes_adicionais: int = Field(default=0)


# ---------------------------------------------------------------------------
# Rotas públicas (sem chave)
# ---------------------------------------------------------------------------
@app.get("/health", tags=["público"])
def health() -> dict:
    """Health check — público."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Rotas protegidas (exigem X-API-Key + rate limit)
# ---------------------------------------------------------------------------
@app.get("/tipos", tags=["protegido"], dependencies=[Depends(verificar_api_key)])
@limiter.limit("30/minute")
def tipos(request: Request) -> dict:
    """Lista os tipos de ato suportados."""
    return {
        "tipos": [
            {"valor": t.value, "tem_valor": t.tem_valor}
            for t in TipoAto
        ]
    }


@app.post("/calcular", tags=["protegido"], dependencies=[Depends(verificar_api_key)])
@limiter.limit("30/minute")
def calcular_endpoint(request: Request, pedido: PedidoCalculo) -> dict:
    """Calcula o emolumento de um ato e devolve o breakdown detalhado."""
    try:
        tipo = TipoAto(pedido.tipo)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de ato inválido: {pedido.tipo!r}.",
        ) from None

    try:
        objetos = tuple(parse_valor(v) for v in pedido.valores)
    except EmolumentoError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    if tipo.tem_valor and not objetos:
        raise HTTPException(
            status_code=400,
            detail="Informe ao menos um valor para este tipo de ato.",
        )

    ato = Ato(
        tipo=tipo,
        objetos=objetos,
        usufruto=pedido.usufruto,
        partes_adicionais=pedido.partes_adicionais,
    )

    try:
        resultado = calcular(ato)
    except EmolumentoError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    return resultado_para_dict(resultado)
