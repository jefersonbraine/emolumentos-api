"""API de cálculo de emolumentos de cartório do Paraná.

Casca HTTP fina sobre a biblioteca `emolumentos-pr` que será instalada do PyPI. A regra
de negócio inteira mora na lib, esta API só recebe o pedido, chama `calcular` e
devolve o JSON. É o mesmo padrão da CLI, mas com roupa de web.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from emolumentos_pr import (
    Ato, 
    TipoAto,
    calcular,
    parse_valor,
    resultado_para_dict,
)

from emolumentos_pr.erros import EmolumentoError

app = FastAPI(
    title="API de Emolumentos PR",
    description="Cálculo de emolumentos de cartório do Paraná (Tabela XI). Motor: emolumentos-pr.",
    version="0.1.0",
)

# CORS: libera o front-end (Angular) a chamar a API do navegador.
# Em produção, troque ["*"] pelo domínio real do site.

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"]
)

class PedidoCalculo(BaseModel):
    """Corpo do POST /calcular."""

    tipo: str = Field(..., examples=["compra_e_venda"])
    valores: list[str] = Field(
        default_factory=list,
        description="Valores dos imóveis (aceita '250.000,00' ou '250000'). Vazio p/ atos sem valor.",
        examples=["250.000,00", "250000"]
    )

    usufruto: bool = Field(default=False, description="Doação com usufruto (dobra o Funrejus).")
    partes_adicionais: int = Field(default=0, description="Procuração: partes além da 1ª de cada polo.")

@app.get("/health")
def health() -> dict:
    """Lista os tipos de ato suportados (para o front montar o seletor)."""
    return {
        "tipos": [
            {"valor": t.value, "tem_valor": t.tem_valor}
            for t in TipoAto
        ]
    }

@app.post("/calcular")
def calcular_endpoint(pedido: PedidoCalculo) -> dict:
    """Calcula o emolumento de um ato e devolve o breakdown detalhado."""
    try:
        tipo = TipoAto(pedido.tipo)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Tipo de ato inválido: {pedido.tipo!r}.") from None
    
    try:
        objetos = tuple(parse_valor(v) for v in pedido.valores)
    except EmolumentoError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    
    if tipo.tem_valor and not objetos:
        raise HTTPException(status_code=400, detail="Informe ao menos um valor para este tipo de ato.")
    
    ato = Ato(
        tipo=tipo,
        objetos=objetos,
        usufruto=pedido.usufruto,
        partes_adicionais=pedido.partes_adicionais
    )

    try:
        resultado = calcular(ato)
    except EmolumentoError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    
    return resultado_para_dict(resultado)