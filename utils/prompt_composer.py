"""
Camada central de composição de prompt do Media Rats - Artgen.

Responsável por montar o prompt final enviado ao chat, combinando de forma
estruturada e determinística:

  1. Perfil do cliente  — contexto persistente (identidade, estilo, tom).
  2. Prompt principal    — a instrução específica da arte atual.
  3. Variações           — refinamentos/complementos da série (até 10).

Nenhuma outra parte do sistema deve montar payload de prompt.
Toda composição deve passar por `compor_prompt_arte()`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from excel.reader import Cliente

# ──────────────────────────────────────────────────────────────────────
# Limites
# ──────────────────────────────────────────────────────────────────────
MAX_VARIACOES = 10


# ──────────────────────────────────────────────────────────────────────
# Perfil do cliente (DTO leve para desacoplar da planilha)
# ──────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class PerfilCliente:
    """Representação normalizada do perfil do cliente para composição de prompt.

    Campos vazios são aceitos — a composição os omite automaticamente.
    """

    codigo: str = ""
    nome: str = ""
    nicho: str = ""
    descricao: str = ""
    publico_alvo: str = ""
    formalidade: str = ""
    estilo_visual: str = ""
    estilo_foto: str = ""
    cor_primaria: str = ""
    cor_secundaria: str = ""
    cor_fundo: str = ""

    @classmethod
    def from_cliente(cls, cliente: "Cliente") -> "PerfilCliente":
        """Constrói a partir de um objeto ``excel.reader.Cliente``.

        Normaliza strings: strip, colapsa espaços múltiplos.

        Args:
            cliente: Instância de Cliente lida da planilha.

        Returns:
            PerfilCliente normalizado.
        """
        def _n(valor: str) -> str:
            if not valor:
                return ""
            return " ".join(str(valor).split())

        return cls(
            codigo=_n(cliente.codigo).upper(),
            nome=_n(cliente.nome),
            nicho=_n(cliente.nicho),
            descricao=_n(cliente.descricao),
            publico_alvo=_n(cliente.publico_alvo),
            formalidade=_n(cliente.formalidade),
            estilo_visual=_n(cliente.estilo_visual),
            estilo_foto=_n(cliente.estilo_foto),
            cor_primaria=_n(cliente.cor_primaria),
            cor_secundaria=_n(cliente.cor_secundaria),
            cor_fundo=_n(cliente.cor_fundo),
        )

    @property
    def vazio(self) -> bool:
        """True se o perfil não possui nenhum campo informativo preenchido."""
        return not any([
            self.nicho, self.descricao, self.publico_alvo,
            self.formalidade, self.estilo_visual, self.estilo_foto,
            self.cor_primaria, self.cor_secundaria, self.cor_fundo,
        ])


# ──────────────────────────────────────────────────────────────────────
# Utilitários internos
# ──────────────────────────────────────────────────────────────────────

def _normalizar_texto(texto: str) -> str:
    """Remove espaços excedentes e retorna string limpa."""
    if not texto:
        return ""
    return " ".join(str(texto).split()).strip()


def _limpar_variacoes(variacoes: List[str], excluir_indice: int = -1) -> List[str]:
    """Normaliza, deduplicata e limita variações a MAX_VARIACOES.

    Args:
        variacoes: Lista bruta de variações.
        excluir_indice: Índice da variação que é o prompt principal
                        (será excluída da lista de variações complementares).

    Returns:
        Lista limpa, sem duplicatas, limitada a MAX_VARIACOES.
    """
    vistos: set = set()
    resultado: List[str] = []

    for i, v in enumerate(variacoes):
        if i == excluir_indice:
            continue
        texto = _normalizar_texto(v)
        if not texto:
            continue
        chave = texto.lower()
        if chave in vistos:
            continue
        vistos.add(chave)
        resultado.append(texto)
        if len(resultado) >= MAX_VARIACOES:
            break

    return resultado


def _bloco_perfil(perfil: PerfilCliente) -> str:
    """Monta a seção de perfil do cliente para o prompt composto.

    Campos vazios são omitidos para manter o prompt enxuto.

    Args:
        perfil: PerfilCliente normalizado.

    Returns:
        String formatada ou vazia se o perfil estiver vazio.
    """
    if perfil.vazio and not perfil.nome:
        return ""

    linhas: List[str] = ["══ PERFIL DO CLIENTE ══"]

    if perfil.nome or perfil.codigo:
        id_str = perfil.nome or perfil.codigo
        if perfil.codigo and perfil.nome:
            id_str = f"{perfil.nome} ({perfil.codigo})"
        linhas.append(f"Cliente: {id_str}")

    campos = [
        ("Nicho", perfil.nicho),
        ("Descrição", perfil.descricao),
        ("Público-alvo", perfil.publico_alvo),
        ("Formalidade", perfil.formalidade),
        ("Estilo visual", perfil.estilo_visual),
        ("Estilo fotográfico", perfil.estilo_foto),
    ]
    for rotulo, valor in campos:
        if valor:
            linhas.append(f"{rotulo}: {valor}")

    cores: List[str] = []
    if perfil.cor_primaria:
        cores.append(f"Primária {perfil.cor_primaria}")
    if perfil.cor_secundaria:
        cores.append(f"Secundária {perfil.cor_secundaria}")
    if perfil.cor_fundo:
        cores.append(f"Fundo {perfil.cor_fundo}")
    if cores:
        linhas.append(f"Paleta de cores: {' | '.join(cores)}")

    return "\n".join(linhas)


def _bloco_objetivo(tema: str) -> str:
    """Monta a seção de objetivo/tema."""
    tema = _normalizar_texto(tema)
    if not tema:
        return ""
    return f"══ OBJETIVO DA PEÇA ══\nTema: {tema}"


def _bloco_prompt_principal(prompt: str, numero: int = 0, total: int = 0) -> str:
    """Monta a seção do prompt principal (a instrução da arte atual)."""
    prompt = _normalizar_texto(prompt)
    if not prompt:
        return ""
    cabecalho = "══ INSTRUÇÃO PRINCIPAL"
    if numero > 0 and total > 0:
        cabecalho += f" (Arte {numero}/{total})"
    cabecalho += " ══"
    return f"{cabecalho}\n{prompt}"


def _bloco_variacoes(variacoes: List[str]) -> str:
    """Monta a seção de variações complementares."""
    if not variacoes:
        return ""
    linhas = ["══ VARIAÇÕES COMPLEMENTARES ══"]
    for i, v in enumerate(variacoes, start=1):
        linhas.append(f"[{i}] {v}")
    return "\n".join(linhas)


def _bloco_diretrizes(perfil: PerfilCliente) -> str:
    """Monta diretrizes finais baseadas no perfil do cliente.

    Gera instruções acionáveis apenas quando há dados suficientes.
    """
    if perfil.vazio:
        return ""

    linhas = ["══ DIRETRIZES ══"]
    if perfil.estilo_visual:
        linhas.append(f"- Mantenha o estilo visual {perfil.estilo_visual}.")
    if perfil.cor_primaria or perfil.cor_secundaria or perfil.cor_fundo:
        linhas.append("- Respeite a paleta de cores informada no perfil.")
    if perfil.publico_alvo:
        linhas.append(f"- Adapte o tom e linguagem visual ao público: {perfil.publico_alvo}.")
    if perfil.formalidade:
        linhas.append(f"- Nível de formalidade: {perfil.formalidade}.")
    linhas.append("- Preserve coerência com a identidade do cliente em todos os elementos.")

    return "\n".join(linhas)


# ──────────────────────────────────────────────────────────────────────
# Função pública — ÚNICO ponto de composição do projeto
# ──────────────────────────────────────────────────────────────────────

def compor_prompt_arte(
    *,
    perfil: Optional[PerfilCliente] = None,
    tema: str = "",
    prompt_principal: str = "",
    variacoes: Optional[List[str]] = None,
    indice_prompt_principal: int = -1,
    numero_arte: int = 0,
    total_artes: int = 0,
) -> str:
    """Compõe o prompt final estruturado a ser enviado ao chat.

    Combina perfil do cliente, tema, prompt principal e variações numa
    única string hierárquica, determinística e auditável.

    Regras de composição:
        1. O prompt principal é o centro da solicitação.
        2. O perfil do cliente define identidade e restrições.
        3. As variações refinam/expandem sem substituir o prompt principal.
        4. Conflitos: prompt principal tem prioridade sobre variações;
           perfil do cliente atua como restrição persistente.

    Args:
        perfil: PerfilCliente (None = sem contexto de cliente).
        tema: Tema geral da solicitação.
        prompt_principal: Instrução específica da arte sendo gerada.
        variacoes: Lista completa de prompts da solicitação (até 10).
        indice_prompt_principal: Índice do prompt_principal dentro de
            ``variacoes`` (para excluí-lo da seção de variações).
        numero_arte: Número sequencial da arte (ex: 3).
        total_artes: Total de artes na solicitação (ex: 5).

    Returns:
        String composta pronta para envio ao chat.  Nunca retorna string
        vazia — se dados estiverem ausentes, retorna ao menos o prompt
        principal ou um fallback informativo.
    """
    prompt_principal = _normalizar_texto(prompt_principal)

    if not prompt_principal:
        if variacoes:
            limpas = _limpar_variacoes(variacoes)
            prompt_principal = limpas[0] if limpas else ""

    if not prompt_principal:
        return _normalizar_texto(tema) or "(prompt vazio)"

    if perfil is None:
        perfil = PerfilCliente()

    variacoes_limpas = _limpar_variacoes(
        variacoes or [],
        excluir_indice=indice_prompt_principal,
    )

    # --- Montagem hierárquica ---
    blocos: List[str] = []

    bloco = _bloco_perfil(perfil)
    if bloco:
        blocos.append(bloco)

    bloco = _bloco_objetivo(tema)
    if bloco:
        blocos.append(bloco)

    bloco = _bloco_prompt_principal(prompt_principal, numero_arte, total_artes)
    if bloco:
        blocos.append(bloco)

    bloco = _bloco_variacoes(variacoes_limpas)
    if bloco:
        blocos.append(bloco)

    bloco = _bloco_diretrizes(perfil)
    if bloco:
        blocos.append(bloco)

    return "\n\n".join(blocos)
