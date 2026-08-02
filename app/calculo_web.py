"""Composição do resultado para a web: breakdown por imóvel + total geral.

A biblioteca `calcular` devolve o agregado da escritura. Para a tabela da
calculadora (uma linha por imóvel), montamos o detalhe por item chamando a lib
uma vez por imóvel — pegando dele apenas os componentes que são POR OBJETO
(Emolumentos, Funrejus, FUNDEP, ISSQN). Selo e Distribuidor são de nível
escritura e aparecem só no total geral.
"""

from __future__ import annotations

from decimal import Decimal

from emolumentos_pr import Ato, TipoAto, calcular, formatar_brl

PER_OBJETO = ("Emolumentos", "Funrejus", "FUNDEP", "ISSQN")

def _valor(v: Decimal) -> dict:
    return {"raw": str(v), "brl": formatar_brl(v)}

def _componentes_dict(componentes) -> dict:
    """Mapeia a lista de Componente para um dict {nome_minusculo: {raw, brl}}."""
    mapa = {
        "Emolumentos": "emolumentos",
        "Funrejus": "funrejus",
        "Selo": "selo",
        "Distribuidor": "distribuidor",
        "FUNDEP": "fundep",
        "ISSQN": "issqn",
    }
    return {mapa[c.nome]: _valor(c.valor) for c in componentes if c.nome in mapa}

def montar_resposta(
    tipo: TipoAto,
    objetos: tuple[Decimal, ...],
    *,
    usufruto: bool,
    partes_adicionais: int,
) -> dict:
    # Agregado (o total da escritura, com selo e distribuidor corretos).
    agg = calcular(
        Ato(tipo=tipo, objetos=objetos, usufruto=usufruto, partes_adicionais=partes_adicionais)
    )
    total_geral = {
        "valor_base": _valor(sum(objetos, Decimal("0"))),
        **_componentes_dict(agg.componentes),
        "total": _valor(agg.total),
    }

    # Detalhe por imóvel (só para atos com valor e múltiplos objetos).
    itens = []
    if tipo.tem_valor:
        for i, v in enumerate(objetos, start=1):
            r = calcular(Ato(tipo=tipo, objetos=(v,), usufruto=usufruto))
            por_obj = [c for c in r.componentes if c.nome in PER_OBJETO]
            subtotal = sum((c.valor for c in por_obj), Decimal("0"))
            itens.append({
                "descricao": f"Imóvel {i}",
                "valor_base": _valor(v),
                **_componentes_dict(por_obj),
                "total": _valor(subtotal),
            })

    return {"tipo": tipo.value, "itens": itens, "total_geral": total_geral}