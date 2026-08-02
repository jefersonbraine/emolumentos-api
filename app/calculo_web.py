"""Composição do resultado para a web: breakdown por item + total geral.

Todas as colunas do sistema do cartório, por objeto:
- Emolumentos, Funrejus, FUNDEP, ISSQN, VRC → variam com o valor de cada item.
- Selo → 8,00 de traslado por item (mais 8,00 da escritura, só no total geral).
- Distribuidor → 12,45 no 1º item, 0,00 nos demais (cobrado uma vez por escritura).
- Folha → não calculada pela lib; mantida em 0,00 por fidelidade ao sistema.

Regra 100%/80% (item X.b da Tabela XI): qualquer ato com valor e 2+ objetos
aplica automaticamente — o de maior valor paga 100%, os demais 80% (até 9
adicionais). Como o valor de cada item depende do RANKING dele no conjunto
(é o maior ou não), o breakdown por item não pode ser calculado chamando a
lib um objeto de cada vez (isso funcionava só quando cada item era
independente) — por isso a ordenação e a redução são replicadas aqui.
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
    MAX_UNIDADES_ADICIONAIS,
    PERC_UNIDADE_ADICIONAL,
    SELO_ESCRITURA,
    SELO_TRASLADO,
    TETO_EMOLUMENTO_VRC,
    TETO_FUNREJUS,
    VRC_POR_PARTE_ADICIONAL,
    tabela_de,
)
from emolumentos_pr.vrcext import VRCEXT_ATUAL

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


def _emolumento_cheio(valor: Decimal) -> Decimal:
    vrc = min(tabela_de(TipoAto.COMPRA_E_VENDA).emolumento_vrc(valor), TETO_EMOLUMENTO_VRC)
    return (vrc * VRCEXT_ATUAL).quantize(CENTAVO, rounding=ROUND_DOWN)


def _itens_com_valor(objetos: tuple[Decimal, ...], usufruto: bool) -> list[dict]:
    """Breakdown por item para compra e venda / doação, com o item X.b aplicado
    quando há 2+ objetos (ordenados do maior para o menor, 100%/80%)."""
    ordenados = sorted(objetos, reverse=True)[: 1 + MAX_UNIDADES_ADICIONAIS]

    itens = []
    for i, v in enumerate(ordenados):
        cheio = _emolumento_cheio(v)
        vrc_cheio = min(tabela_de(TipoAto.COMPRA_E_VENDA).emolumento_vrc(v), TETO_EMOLUMENTO_VRC)

        if i == 0:
            emol, vrc = cheio, vrc_cheio
        else:
            emol = (cheio * PERC_UNIDADE_ADICIONAL).quantize(CENTAVO, rounding=ROUND_HALF_UP)
            vrc = vrc_cheio * PERC_UNIDADE_ADICIONAL

        funrejus = min(v * ALIQUOTA_FUNREJUS, TETO_FUNREJUS)
        if usufruto:
            funrejus *= 2
        fundep = emol * ALIQUOTA_FUNDEP
        issqn = emol * ALIQUOTA_ISSQN
        selo = SELO_TRASLADO
        distribuidor = DISTRIBUIDOR if i == 0 else ZERO
        subtotal = emol + funrejus + selo + distribuidor + fundep + issqn

        rotulo = f"Item {i + 1}" + (" (maior valor)" if i == 0 and len(ordenados) > 1 else "")
        itens.append({
            "descricao": rotulo,
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
    return itens


def _vrc_total_sem_valor(tipo: TipoAto, partes: int) -> Decimal:
    if tipo is TipoAto.PROCURACAO:
        return EMOLUMENTO_PROCURACAO_VRC + partes * VRC_POR_PARTE_ADICIONAL
    return EMOLUMENTO_SEM_VALOR_VRC


def montar_resposta(
    tipo: TipoAto,
    objetos: tuple[Decimal, ...],
    *,
    usufruto: bool,
    partes_adicionais: int,
) -> dict:
    agg = calcular(
        Ato(tipo=tipo, objetos=objetos, usufruto=usufruto, partes_adicionais=partes_adicionais)
    )

    if tipo.tem_valor:
        itens = _itens_com_valor(objetos, usufruto)
        vrc_total = sum((Decimal(i["vrc"]["raw"]) for i in itens), ZERO)
    else:
        itens = []
        vrc_total = _vrc_total_sem_valor(tipo, partes_adicionais)

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