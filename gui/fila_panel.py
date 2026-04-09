"""
Painel de fila de solicitações do Media Rats - Artgen.
Exibe tabela com status, permite seleção e duplo clique para detalhes.
"""

from __future__ import annotations

from typing import List, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QDialog,
    QTextEdit, QDialogButtonBox, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QFont, QBrush

from excel.reader import Solicitacao


STATUS_CORES = {
    "planejado": ("#FFF9C4", "#F57F17"),
    "pendente":  ("#FFE0B2", "#E65100"),
    "gerando":   ("#BBDEFB", "#0D47A1"),
    "gerado":    ("#C8E6C9", "#1B5E20"),
    "erro":      ("#FFCDD2", "#B71C1C"),
    "cancelado": ("#ECEFF1", "#455A64"),
}

COLUNAS = ["Protocolo", "Cliente", "Tema", "Status", "Data Planejada"]


class DetalheDialog(QDialog):
    """Diálogo que exibe os detalhes completos de uma solicitação.

    Args:
        solicitacao: Dados da solicitação a exibir.
    """

    def __init__(self, solicitacao: Solicitacao, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Detalhes — {solicitacao.protocolo}")
        self.setMinimumSize(560, 420)
        self.setStyleSheet(
            "QDialog { background-color: #121212; color: #E0E0E0; }"
        )
        layout = QVBoxLayout(self)

        info = (
            f"Protocolo:  {solicitacao.protocolo}\n"
            f"Cliente:    {solicitacao.cliente}\n"
            f"Código:     {solicitacao.codigo_cliente}\n"
            f"Tema:       {solicitacao.tema}\n"
            f"Status:     {solicitacao.status}\n"
            f"Data Plan.: {solicitacao.data_planejada or '—'}\n"
            f"\n{'─' * 50}\nPROMPTS\n{'─' * 50}"
        )
        for i, p in enumerate(solicitacao.prompts, start=1):
            if p and p.strip():
                info += f"\n[{i:02d}] {p}"

        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText(info)
        text.setFont(QFont("Consolas", 10))
        text.setStyleSheet(
            "QTextEdit { background: #1E1E1E; color: #E0E0E0; "
            "border: 1px solid #333; border-radius: 4px; padding: 8px; }"
        )
        layout.addWidget(text)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.reject)
        btns.setStyleSheet("QPushButton { background:#263238; color:#E0E0E0; border:none; "
                           "border-radius:4px; padding:6px 18px; }"
                           "QPushButton:hover { background:#37474F; }")
        layout.addWidget(btns)


class FilaPanel(QWidget):
    """Painel que exibe a fila de solicitações em formato tabela."""

    solicitacao_selecionada = pyqtSignal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._solicitacoes: List[Solicitacao] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header = QHBoxLayout()
        titulo = QLabel("📋 Fila de Solicitações")
        titulo.setStyleSheet("color: #E0E0E0; font-weight: bold; font-size: 13px;")
        header.addWidget(titulo)
        header.addStretch()
        self._lbl_total = QLabel("0 itens")
        self._lbl_total.setStyleSheet("color: #607D8B; font-size: 11px;")
        header.addWidget(self._lbl_total)
        layout.addLayout(header)

        self._tabela = QTableWidget()
        self._tabela.setColumnCount(len(COLUNAS))
        self._tabela.setHorizontalHeaderLabels(COLUNAS)
        self._tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tabela.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tabela.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tabela.setAlternatingRowColors(False)
        self._tabela.verticalHeader().setVisible(False)
        self._tabela.horizontalHeader().setStretchLastSection(True)
        self._tabela.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._tabela.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._tabela.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._tabela.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._tabela.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._tabela.setShowGrid(False)
        self._tabela.setStyleSheet(
            "QTableWidget { background-color: #0D1117; color: #C9D1D9; "
            "border: 1px solid #30363D; border-radius: 6px; gridline-color: #21262D; }"
            "QTableWidget::item { padding: 6px 10px; border-bottom: 1px solid #21262D; }"
            "QTableWidget::item:selected { background-color: #1565C0; color: #FFFFFF; }"
            "QHeaderView::section { background-color: #161B22; color: #8B949E; "
            "border: none; border-bottom: 1px solid #30363D; padding: 6px 10px; font-weight: bold; }"
        )
        self._tabela.doubleClicked.connect(self._abrir_detalhe)
        self._tabela.selectionModel().selectionChanged.connect(self._on_selecao_mudou)
        layout.addWidget(self._tabela)

    def carregar_solicitacoes(self, solicitacoes: List[Solicitacao]) -> None:
        """Carrega lista de solicitações na tabela.

        Args:
            solicitacoes: Lista de objetos Solicitacao.
        """
        self._solicitacoes = solicitacoes
        self._tabela.setRowCount(0)
        for sol in solicitacoes:
            self._adicionar_linha(sol)
        self._lbl_total.setText(f"{len(solicitacoes)} item(s)")

    def _adicionar_linha(self, sol: Solicitacao) -> None:
        """Adiciona uma linha à tabela para a solicitação.

        Args:
            sol: Solicitação a adicionar.
        """
        row = self._tabela.rowCount()
        self._tabela.insertRow(row)
        self._tabela.setRowHeight(row, 34)

        data_str = sol.data_planejada.strftime("%d/%m/%Y") if sol.data_planejada else "—"
        valores = [sol.protocolo, sol.cliente, sol.tema, sol.status, data_str]

        status_key = sol.status.lower()
        bg_hex, fg_hex = STATUS_CORES.get(status_key, ("#1E2A38", "#E0E0E0"))

        for col, val in enumerate(valores):
            item = QTableWidgetItem(val)
            item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            if col == 3:
                item.setBackground(QBrush(QColor(bg_hex)))
                item.setForeground(QBrush(QColor(fg_hex)))
                item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            else:
                item.setForeground(QBrush(QColor("#C9D1D9")))
            self._tabela.setItem(row, col, item)

    def atualizar_status_linha(self, protocolo: str, novo_status: str) -> None:
        """Atualiza o status de uma linha na tabela.

        Args:
            protocolo: Protocolo da solicitação a atualizar.
            novo_status: Novo status a exibir.
        """
        for row in range(self._tabela.rowCount()):
            item_proto = self._tabela.item(row, 0)
            if item_proto and item_proto.text() == protocolo:
                item_status = self._tabela.item(row, 3)
                if item_status:
                    item_status.setText(novo_status)
                    bg_hex, fg_hex = STATUS_CORES.get(novo_status.lower(), ("#1E2A38", "#E0E0E0"))
                    item_status.setBackground(QBrush(QColor(bg_hex)))
                    item_status.setForeground(QBrush(QColor(fg_hex)))
                for sol in self._solicitacoes:
                    if sol.protocolo == protocolo:
                        sol.status = novo_status
                break

    def solicitacao_atual(self) -> Optional[Solicitacao]:
        """Retorna a solicitação selecionada na tabela.

        Returns:
            Objeto Solicitacao selecionado ou None.
        """
        indices = self._tabela.selectedIndexes()
        if not indices:
            return None
        row = indices[0].row()
        if row < len(self._solicitacoes):
            return self._solicitacoes[row]
        return None

    def remover_solicitacao(self, protocolo: str) -> bool:
        """Remove uma solicitação da tabela e da lista interna pelo protocolo.

        Args:
            protocolo: Identificador único da solicitação (ex: DUDE#1).

        Returns:
            True se a remoção foi efetuada, False se não encontrou o protocolo.
        """
        for row in range(self._tabela.rowCount()):
            item = self._tabela.item(row, 0)
            if item and item.text() == protocolo:
                self._tabela.removeRow(row)
                self._solicitacoes = [
                    s for s in self._solicitacoes if s.protocolo != protocolo
                ]
                self._lbl_total.setText(f"{len(self._solicitacoes)} item(s)")
                return True
        return False

    def _on_selecao_mudou(self) -> None:
        """Emite sinal com a solicitação selecionada."""
        sol = self.solicitacao_atual()
        if sol:
            self.solicitacao_selecionada.emit(sol)

    def _abrir_detalhe(self) -> None:
        """Abre diálogo de detalhes ao dar duplo clique na linha."""
        sol = self.solicitacao_atual()
        if sol:
            dlg = DetalheDialog(sol, self)
            dlg.exec()
