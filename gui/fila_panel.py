"""
Painel de fila de solicitações do Media Rats - Artgen.
Exibe tabela com status, permite seleção e duplo clique para detalhes.
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QDialog,
    QTextEdit, QDialogButtonBox, QFrame, QLineEdit, QCheckBox, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QFont, QBrush

from excel.reader import Solicitacao
from utils.status import STATUS_CORES_GUI as STATUS_CORES, STATUS_VALIDOS

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
            "QDialog { background-color: #000000; color: #d0d0d0; }"
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
            "QTextEdit { background: #0d0d0d; color: #c0d0c0; "
            "border: 1px solid #1a3a1a; border-radius: 4px; padding: 8px; }"
        )
        layout.addWidget(text)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.reject)
        btns.setStyleSheet("QPushButton { background:#111111; color:#d0d0d0; border:1px solid #1a3a1a; "
                           "border-radius:4px; padding:6px 18px; }"
                           "QPushButton:hover { background:#003300; color:#00ff00; }")
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
        titulo = QLabel("Fila de Solicitações")
        titulo.setStyleSheet("color: #00cc00; font-weight: bold; font-size: 13px;")
        header.addWidget(titulo)
        header.addStretch()
        self._lbl_total = QLabel("0 itens")
        self._lbl_total.setStyleSheet("color: #336633; font-size: 11px;")
        header.addWidget(self._lbl_total)
        layout.addLayout(header)

        filtros = QHBoxLayout()
        filtros.setSpacing(8)

        self._inp_busca = QLineEdit()
        self._inp_busca.setPlaceholderText("🔍  Buscar protocolo, cliente ou tema...")
        self._inp_busca.setStyleSheet(
            "QLineEdit { background: #0d0d0d; color: #c0c0c0; border: 1px solid #1a3a1a; "
            "border-radius: 4px; padding: 4px 8px; font-size: 11px; }"
            "QLineEdit:focus { border-color: #00aa00; }"
        )
        self._inp_busca.textChanged.connect(self._aplicar_filtros)
        filtros.addWidget(self._inp_busca)

        self._chk_hoje = QCheckBox("Apenas hoje / atrasadas")
        self._chk_hoje.setStyleSheet(
            "QCheckBox { color: #888888; font-size: 11px; spacing: 6px; }"
            "QCheckBox::indicator { width: 14px; height: 14px; border: 1px solid #282828; "
            "border-radius: 3px; background: #111111; }"
            "QCheckBox::indicator:checked { background: #004400; border-color: #00aa00; }"
        )
        self._chk_hoje.stateChanged.connect(self._aplicar_filtros)
        filtros.addWidget(self._chk_hoje)

        self._cmb_status = QComboBox()
        self._cmb_status.addItem("Todos os status")
        for s in sorted(STATUS_VALIDOS):
            self._cmb_status.addItem(s)
        self._cmb_status.setFixedWidth(150)
        self._cmb_status.setStyleSheet(
            "QComboBox { background: #0d0d0d; color: #c0c0c0; border: 1px solid #1a3a1a; "
            "border-radius: 4px; padding: 3px 8px; font-size: 11px; }"
            "QComboBox::drop-down { border: none; }"
            "QComboBox QAbstractItemView { background: #0d0d0d; color: #c0c0c0; "
            "border: 1px solid #1a3a1a; selection-background-color: #002200; }"
        )
        self._cmb_status.currentTextChanged.connect(self._aplicar_filtros)
        filtros.addWidget(self._cmb_status)

        layout.addLayout(filtros)

        self._tabela = QTableWidget()
        self._tabela.setColumnCount(len(COLUNAS))
        self._tabela.setHorizontalHeaderLabels(COLUNAS)
        self._tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tabela.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tabela.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tabela.setAlternatingRowColors(False)
        self._tabela.verticalHeader().setVisible(False)
        self._tabela.horizontalHeader().setStretchLastSection(False)
        self._tabela.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._tabela.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._tabela.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._tabela.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._tabela.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._tabela.horizontalHeader().setMinimumSectionSize(60)
        self._tabela.setShowGrid(False)
        self._tabela.setSortingEnabled(True)
        self._tabela.setStyleSheet(
            "QTableWidget { background-color: #000000; color: #c0c0c0; "
            "border: 1px solid #1a3a1a; border-radius: 6px; gridline-color: #111111; }"
            "QTableWidget::item { padding: 6px 10px; border-bottom: 1px solid #0d0d0d; }"
            "QTableWidget::item:selected { background-color: #002200; color: #00ff00; }"
            "QHeaderView::section { background-color: #000000; color: #00aa00; "
            "border: none; border-bottom: 1px solid #1a3a1a; padding: 6px 10px; font-weight: bold; letter-spacing: 0.5px; }"
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
        self._tabela.setSortingEnabled(False)
        self._tabela.setRowCount(0)
        for sol in solicitacoes:
            self._adicionar_linha(sol)
        self._tabela.setSortingEnabled(True)
        self._lbl_total.setText(f"{len(solicitacoes)} item(s)")
        self._aplicar_filtros()

    def _aplicar_filtros(self) -> None:
        """Aplica filtro de texto e/ou data_planejada às linhas da tabela."""
        texto = self._inp_busca.text().strip().lower()
        apenas_hoje = self._chk_hoje.isChecked()
        hoje = date.today()
        visiveis = 0

        filtro_status = self._cmb_status.currentText()

        for row in range(self._tabela.rowCount()):
            item0 = self._tabela.item(row, 0)
            sol = item0.data(Qt.ItemDataRole.UserRole) if item0 else None

            if sol is None:
                self._tabela.setRowHidden(row, True)
                continue

            if filtro_status and filtro_status != "Todos os status":
                if sol.status.lower() != filtro_status.lower():
                    self._tabela.setRowHidden(row, True)
                    continue

            if apenas_hoje:
                data = sol.data_planejada
                if data is not None and data > hoje:
                    self._tabela.setRowHidden(row, True)
                    continue

            if texto:
                colunas_busca = [sol.protocolo, sol.cliente, sol.tema, sol.status]
                if not any(texto in (v or "").lower() for v in colunas_busca):
                    self._tabela.setRowHidden(row, True)
                    continue

            self._tabela.setRowHidden(row, False)
            visiveis += 1

        total = len(self._solicitacoes)
        if visiveis == total:
            self._lbl_total.setText(f"{total} item(s)")
        else:
            self._lbl_total.setText(f"{visiveis} de {total} item(s)")

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
            if col == 0:
                item.setData(Qt.ItemDataRole.UserRole, sol)
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
        item0 = self._tabela.item(row, 0)
        if item0:
            return item0.data(Qt.ItemDataRole.UserRole)
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
