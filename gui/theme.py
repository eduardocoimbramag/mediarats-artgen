"""
Constantes e helpers de tema visual do Media Rats - Artgen.

Centraliza todas as cores e funções de estilo usadas pela GUI, eliminando
strings de estilo duplicadas em múltiplos arquivos. Para mudar o tema,
edite apenas este arquivo.
"""

from __future__ import annotations

# ── Cores base ────────────────────────────────────────────────────────────────
FUNDO_PRINCIPAL    = "#000000"
FUNDO_CARD         = "#0d0d0d"
FUNDO_INPUT        = "#111111"

VERDE_PRIMARIO     = "#00ff00"
VERDE_MEDIO        = "#00cc00"
VERDE_ESCURO       = "#003300"
VERDE_ESCURO_HOVER = "#004400"
VERDE_BORDA        = "#1a3a1a"
VERDE_BORDA_SUTIL  = "#1a2a1a"

TEXTO_PRINCIPAL    = "#d0d0d0"
TEXTO_SECUNDARIO   = "#c0c0c0"
TEXTO_MUTED        = "#888888"
TEXTO_VERDE_MUTED  = "#336633"

BORDA_INPUT        = "#282828"

COR_AVISO          = "#FF9800"
COR_ERRO           = "#F44336"
COR_SELECAO_BG     = "#002200"

RAIO_CARD  = "8px"
RAIO_INPUT = "4px"
RAIO_BOTAO = "4px"

# ── Helpers de estilo ─────────────────────────────────────────────────────────

def estilo_card(extra: str = "") -> str:
    """Estilo padrão para widgets tipo card (fundo escuro + borda verde)."""
    base = (
        f"background-color: {FUNDO_CARD}; "
        f"border: 1px solid {VERDE_BORDA}; "
        f"border-radius: {RAIO_CARD};"
    )
    return base + (" " + extra if extra else "")


def estilo_input(extra: str = "") -> str:
    """Estilo padrão para campos de entrada de texto."""
    base = (
        f"background-color: {FUNDO_INPUT}; "
        f"color: {TEXTO_PRINCIPAL}; "
        f"border: 1px solid {BORDA_INPUT}; "
        f"border-radius: {RAIO_INPUT}; "
        "padding: 5px 8px;"
    )
    return base + (" " + extra if extra else "")


def estilo_botao_primario() -> str:
    """Estilo para botão de ação principal (verde)."""
    return (
        f"QPushButton {{ background: {VERDE_ESCURO}; color: {VERDE_PRIMARIO}; "
        f"border: 1px solid {VERDE_BORDA}; border-radius: {RAIO_BOTAO}; "
        "padding: 6px 12px; font-weight: bold; }}"
        f"QPushButton:hover {{ background: {VERDE_ESCURO_HOVER}; color: {VERDE_PRIMARIO}; }}"
        "QPushButton:disabled { background: #111111; color: #333333; border-color: #1a1a1a; }"
    )


def estilo_botao_secundario() -> str:
    """Estilo para botão secundário (cinza discreto)."""
    return (
        f"QPushButton {{ background: {FUNDO_INPUT}; color: {TEXTO_MUTED}; "
        f"border: 1px solid {VERDE_BORDA_SUTIL}; border-radius: {RAIO_BOTAO}; "
        "padding: 6px 12px; }}"
        f"QPushButton:hover {{ background: {VERDE_ESCURO}; color: {VERDE_MEDIO}; }}"
    )


def estilo_label_titulo() -> str:
    """Estilo para títulos de seção."""
    return f"color: {VERDE_MEDIO}; font-weight: bold; font-size: 13px;"


def estilo_label_muted() -> str:
    """Estilo para textos de suporte/rodapé."""
    return f"color: {TEXTO_VERDE_MUTED}; font-size: 11px;"


def estilo_status_bar() -> str:
    """Estilo para a QStatusBar."""
    return (
        f"QStatusBar {{ background: {FUNDO_PRINCIPAL}; color: #444444; "
        f"font-size: 11px; border-top: 1px solid {VERDE_BORDA_SUTIL}; }}"
    )


def estilo_tabela() -> str:
    """Estilo completo para QTableWidget."""
    return (
        f"QTableWidget {{ background-color: {FUNDO_PRINCIPAL}; color: {TEXTO_SECUNDARIO}; "
        f"border: 1px solid {VERDE_BORDA}; border-radius: 6px; "
        f"gridline-color: {FUNDO_CARD}; }}"
        f"QTableWidget::item {{ padding: 6px 10px; border-bottom: 1px solid {FUNDO_CARD}; }}"
        f"QTableWidget::item:selected {{ background-color: {COR_SELECAO_BG}; "
        f"color: {VERDE_PRIMARIO}; }}"
        f"QHeaderView::section {{ background-color: {FUNDO_PRINCIPAL}; color: {VERDE_MEDIO}; "
        f"border: none; border-bottom: 1px solid {VERDE_BORDA}; "
        "padding: 6px 10px; font-weight: bold; letter-spacing: 0.5px; }}"
    )


def estilo_dialog() -> str:
    """Estilo base para QDialog."""
    return f"QDialog {{ background-color: {FUNDO_PRINCIPAL}; color: {TEXTO_SECUNDARIO}; }}"


def estilo_scroll_area() -> str:
    """Estilo para QScrollArea."""
    return (
        f"QScrollArea {{ border: 1px solid {VERDE_BORDA}; border-radius: 6px; "
        f"background: {FUNDO_PRINCIPAL}; }}"
    )
