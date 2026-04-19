"""
Fonte única de verdade para status de solicitações e suas cores.

Centraliza os valores válidos e as paletas de cores usadas tanto pela
planilha Excel (``STATUS_CORES_EXCEL``) quanto pela GUI PyQt6
(``STATUS_CORES_GUI``), eliminando a duplicação entre
``excel/writer.py`` e ``gui/fila_panel.py``.

Para adicionar um novo status, edite apenas este arquivo.
"""

from __future__ import annotations

STATUS_VALIDOS: frozenset = frozenset({
    "Planejado",
    "Pendente",
    "Gerando",
    "Gerado",
    "Erro",
    "Cancelado",
})

STATUS_CORES_EXCEL: dict[str, str] = {
    "Planejado":  "FFF9C4",
    "Pendente":   "FFE0B2",
    "Gerando":    "BBDEFB",
    "Gerado":     "C8E6C9",
    "Erro":       "FFCDD2",
    "Cancelado":  "E0E0E0",
}

STATUS_CORES_GUI: dict[str, tuple[str, str]] = {
    "planejado": ("#1e1800", "#ccaa00"),
    "pendente":  ("#1e0e00", "#cc6600"),
    "gerando":   ("#001a00", "#00cc00"),
    "gerado":    ("#002200", "#00ff00"),
    "erro":      ("#1e0000", "#cc3333"),
    "cancelado": ("#141414", "#666666"),
}
