"""Composição do resultado para a web: breakdown por imóvel + total geral.

Todas as colunas do sistema do cartório, por objeto:
- Emolumentos, Funrejus, FUNDEP, ISSQN, VRC → variam com o valor de cada imóvel.
- Selo → 8,00 de traslado por imóvel (mais 8,00 da escritura, só no total geral).
- Distribuidor → 12,45 no 1º imóvel, 0,00 nos demais (cobrado uma vez por escritura).
- Folha → não calculada pela lib; mantida em 0,00 por fidelidade ao sistema.

Partilha (inventário/divórcio) tem regra própria: o bem de maior valor paga 100%
do emolumento, os demais pagam 80% — Funrejus/FUNDEP/ISSQN seguem cheios. Como
o valor de cada bem depende do RANKING dele no conjunto, ela não pode ser
calculada bem a bem isoladamente (diferente de compra e venda/doação), por isso
tem sua própria função de composição (_montar_resposta_partilha).
"""

from __future__ import annotations

from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

from emolumentos_pr import Ato, TipoAto, calcular, formatar_brl
from emolumentos_pr.tabelas import (
    ALIQUOTA_FUNDEP,
    ALIQUOTA_ISSQN,
    ALIQUOTA_FUNREJUS,
    DISTRIBUIDOR,
    EMOLUMENTO_PROCURACAO_VRC,
    EMOLUMENTO_SEM_VALOR_VRC,
    PERC_UNIDADE_ADICIONAL,
    SELO_ESCRITURA,
    SELO_TRASLADO,
    TETO_EMOLUMENTO_VRC,
    TETO_FUNREJUS,
    VRC_POR_PARTE_ADICIONAL,
    tabela_de,
)
from emolumentos_pr.vrcext import VRCEXT_ATUAL

SELO_TRASLADO_VAL = Decimal("8.00")
DISTRIBUIDOR_VAL = Decimal("12.45")
CENTAVO = Decimal("0.01")
ZERO = Decimal("0")


def _brl(v: Decimal) -> dict:
    return {"raw": str(v), "brl": formatar_brl(v)}


def _num(v: Decimal) -> dict:
    """VRC formatado como número pt-BR simples (sem 'R$')."""
    return {"raw": str(v), "fmt": formatar_brl(v).replace("R$ ", "")}


def _comp(componentes, nome: str) -> Decimal:
    for c in componentes:
        if c.nome == nome:
            return c.valor
    return ZERO


def _vrc_de(tipo: TipoAto, valor: Decimal, partes: int) -> Decimal:
    if tipo.tem_valor:
        return min(tabela_de(tipo).emolumento_vrc(valor), TETO_EMOLUMENTO_VRC)
    if tipo is TipoAto.PROCURACAO:
        return EMOLUMENTO_PROCURACAO_VRC + partes * VRC_POR_PARTE_ADICIONAL
    return EMOLUMENTO_SEM_VALOR_VRC


def _emolumento_cheio(valor: Decimal) -> Decimal:
    vrc = min(tabela_de(TipoAto.COMPRA_E_VENDA).emolumento_vrc(valor), TETO_EMOLUMENTO_VRC)
    return (vrc * VRCEXT_ATUAL).quantize(CENTAVO, rounding=ROUND_DOWN)


# ---------------------------------------------------------------------------
# Partilha — regra própria (100% / 80%, dependente do ranking dos bens)
# ---------------------------------------------------------------------------
def _montar_resposta_partilha(objetos: tuple[Decimal, ...], partes_adicionais: int) -> dict:
    ordenados = sorted(objetos, reverse=True)

    itens = []
    for i, v in enumerate(ordenados):
        cheio = _emolumento_cheio(v)
        vrc_cheio = min(tabela_de(TipoAto.COMPRA_E_VENDA).emolumento_vrc(v), TETO_EMOLUMENTO_VRC)

        if i == 0:
            emol = cheio
            vrc = vrc_cheio
        else:
            emol = (cheio * PERC_UNIDADE_ADICIONAL).quantize(CENTAVO, rounding=ROUND_HALF_UP)
            vrc = vrc_cheio * PERC_UNIDADE_ADICIONAL

        funrejus = min(v * ALIQUOTA_FUNREJUS, TETO_FUNREJUS)
        fundep = emol * ALIQUOTA_FUNDEP
        issqn = emol * ALIQUOTA_ISSQN
        selo = SELO_TRASLADO_VAL
        distribuidor = DISTRIBUIDOR_VAL if i == 0 else ZERO
        subtotal = emol + funrejus + selo + distribuidor + fundep + issqn

        itens.append({
            "descricao": f"Bem {i + 1}" + (" (maior valor)" if i == 0 else ""),
            "valor_base": _brl(v),
            "emolumentos": _brl(emol),
            "funrejus": _brl(funrejus),
            "selo": _brl(selo),
            "distribuidor": _brl(distribuidor),
            "folha": _brl(ZERO),
            "fundep": _brl(fundep),
            "issqn": _brl(issqn),
            "vrc": _num(vrc),
            "total": _brl(subtotal),
        })

    ato = Ato(tipo=TipoAto.PARTILHA, objetos=tuple(ordenados), partes_adicionais=partes_adicionais)
    agg = calcular(ato)

    vrc_total = sum(
        (min(tabela_de(TipoAto.COMPRA_E_VENDA).emolumento_vrc(v), TETO_EMOLUMENTO_VRC)
         * (Decimal("1") if i == 0 else PERC_UNIDADE_ADICIONAL)
         for i, v in enumerate(ordenados)),
        ZERO,
    )

    total_geral = {
        "valor_base": _brl(sum(objetos, ZERO)),
        "emolumentos": _brl(_comp(agg.componentes, "Emolumentos")),
        "funrejus": _brl(_comp(agg.componentes, "Funrejus")),
        "selo": _brl(_comp(agg.componentes, "Selo")),
        "distribuidor": _brl(_comp(agg.componentes, "Distribuidor")),
        "folha": _brl(ZERO),
        "fundep": _brl(_comp(agg.componentes, "FUNDEP")),
        "issqn": _brl(_comp(agg.componentes, "ISSQN")),
        "vrc": _num(vrc_total),
        "total": _brl(agg.total),
    }
    return {"tipo": "partilha", "itens": itens, "total_geral": total_geral}


# ---------------------------------------------------------------------------
# Demais atos — cada item é independente (não depende de ranking)
# ---------------------------------------------------------------------------
def montar_resposta(
    tipo: TipoAto,
    objetos: tuple[Decimal, ...],
    *,
    usufruto: bool,
    partes_adicionais: int,
) -> dict:
    if tipo is TipoAto.PARTILHA:
        return _montar_resposta_partilha(objetos, partes_adicionais)

    agg = calcular(
        Ato(tipo=tipo, objetos=objetos, usufruto=usufruto, partes_adicionais=partes_adicionais)
    )

    itens = []
    vrc_total = ZERO
    if tipo.tem_valor:
        for i, v in enumerate(objetos):
            r = calcular(Ato(tipo=tipo, objetos=(v,), usufruto=usufruto))
            emol = _comp(r.componentes, "Emolumentos")
            funrejus = _comp(r.componentes, "Funrejus")
            fundep = _comp(r.componentes, "FUNDEP")
            issqn = _comp(r.componentes, "ISSQN")
            selo = SELO_TRASLADO_VAL
            distribuidor = DISTRIBUIDOR_VAL if i == 0 else ZERO
            vrc = _vrc_de(tipo, v, partes_adicionais)
            vrc_total += vrc
            subtotal = emol + funrejus + selo + distribuidor + fundep + issqn
            itens.append({
                "descricao": f"Imóvel {i + 1}",
                "valor_base": _brl(v),
                "emolumentos": _brl(emol),
                "funrejus": _brl(funrejus),
                "selo": _brl(selo),
                "distribuidor": _brl(distribuidor),
                "folha": _brl(ZERO),
                "fundep": _brl(fundep),
                "issqn": _brl(issqn),
                "vrc": _num(vrc),
                "total": _brl(subtotal),
            })
    else:
        vrc_total = _vrc_de(tipo, ZERO, partes_adicionais)

    total_geral = {
        "valor_base": _brl(sum(objetos, ZERO)),
        "emolumentos": _brl(_comp(agg.componentes, "Emolumentos")),
        "funrejus": _brl(_comp(agg.componentes, "Funrejus")),
        "selo": _brl(_comp(agg.componentes, "Selo")),
        "distribuidor": _brl(_comp(agg.componentes, "Distribuidor")),
        "folha": _brl(ZERO),
        "fundep": _brl(_comp(agg.componentes, "FUNDEP")),
        "issqn": _brl(_comp(agg.componentes, "ISSQN")),
        "vrc": _num(vrc_total),
        "total": _brl(agg.total),
    }

    return {"tipo": tipo.value, "itens": itens, "total_geral": total_geral}