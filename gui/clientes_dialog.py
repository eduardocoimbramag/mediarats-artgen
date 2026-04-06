"""
Diálogo de gerenciamento de clientes do Media Rats - Artgen.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QTableWidget, QTableWidgetItem, QPushButton,
    QMessageBox, QHeaderView, QAbstractItemView, QWidget,
    QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from excel.writer import ExcelWriter


ESTILO_DIALOG = (
    "QDialog { background-color: #121212; color: #E0E0E0; }"
    "QTableWidget { background: #1A1A2E; color: #E0E0E0; "
    "border: 1px solid #30363D; gridline-color: #2D3748; }"
    "QTableWidget::item { padding: 6px; }"
    "QTableWidget::item:selected { background: #1565C0; color: #FFF; }"
    "QHeaderView::section { background: #0D47A1; color: #FFF; font-weight: bold; "
    "padding: 6px; border: none; border-right: 1px solid #1A237E; }"
    "QLineEdit { background: #1E2A38; color: #E0E0E0; border: 1px solid #37474F; "
    "border-radius: 4px; padding: 5px 8px; }"
    "QLineEdit:focus { border-color: #1565C0; }"
    "QLabel { color: #B0BEC5; font-size: 12px; }"
    "QFrame[frameShape='4'] { color: #30363D; }"
)

_CODIGO_RE = re.compile(r"^[A-Za-z]{2,6}$")


def _btn(texto: str, bg: str, hover: str, cor_texto: str = "#FFFFFF") -> QPushButton:
    """Cria um QPushButton estilizado.

    Args:
        texto: Rótulo do botão.
        bg: Cor de fundo normal.
        hover: Cor de fundo ao passar o mouse.
        cor_texto: Cor do texto.

    Returns:
        QPushButton configurado.
    """
    b = QPushButton(texto)
    b.setMinimumHeight(34)
    b.setStyleSheet(
        f"QPushButton {{ background: {bg}; color: {cor_texto}; border: none; "
        f"border-radius: 5px; padding: 5px 14px; font-size: 12px; }}"
        f"QPushButton:hover {{ background: {hover}; }}"
        f"QPushButton:disabled {{ background: #263238; color: #546E7A; }}"
    )
    return b


class _ClienteFormDialog(QDialog):
    """Diálogo interno para cadastrar ou editar um cliente.

    Args:
        titulo: Título da janela.
        codigo_inicial: Código pré-preenchido (edição).
        nome_inicial: Nome pré-preenchido (edição).
        codigo_fixo: Se True, o campo de código fica somente-leitura.
        parent: Widget pai.
    """

    def __init__(
        self,
        titulo: str,
        codigo_inicial: str = "",
        nome_inicial: str = "",
        codigo_fixo: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.setFixedSize(360, 200)
        self.setStyleSheet(ESTILO_DIALOG)
        self._codigo_fixo = codigo_fixo
        self._build_ui(codigo_inicial, nome_inicial, codigo_fixo)

    def _build_ui(self, codigo: str, nome: str, codigo_fixo: bool) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        form = QFormLayout()
        form.setSpacing(10)

        self._inp_codigo = QLineEdit(codigo)
        self._inp_codigo.setPlaceholderText("Ex: DUDE (2-6 letras)")
        self._inp_codigo.setMaxLength(6)
        if codigo_fixo:
            self._inp_codigo.setReadOnly(True)
            self._inp_codigo.setStyleSheet(
                "QLineEdit { background: #263238; color: #78909C; border: 1px solid #37474F; "
                "border-radius: 4px; padding: 5px 8px; }"
            )

        self._inp_nome = QLineEdit(nome)
        self._inp_nome.setPlaceholderText("Nome completo da empresa")

        form.addRow("Código:", self._inp_codigo)
        form.addRow("Nome:", self._inp_nome)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_salvar = _btn("💾  Salvar", "#1565C0", "#1976D2")
        btn_cancelar = _btn("Cancelar", "#263238", "#37474F", "#B0BEC5")
        btn_salvar.clicked.connect(self._validar_e_aceitar)
        btn_cancelar.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(btn_cancelar)
        btn_row.addWidget(btn_salvar)
        layout.addLayout(btn_row)

    def _validar_e_aceitar(self) -> None:
        """Valida os campos e fecha com accept se estiver OK."""
        codigo = self._inp_codigo.text().strip().upper()
        nome = self._inp_nome.text().strip()

        if not _CODIGO_RE.match(codigo):
            QMessageBox.warning(
                self, "Código inválido",
                "O código deve ter entre 2 e 6 letras (sem números ou símbolos)."
            )
            self._inp_codigo.setFocus()
            return

        if not nome:
            QMessageBox.warning(self, "Nome obrigatório", "Preencha o nome do cliente.")
            self._inp_nome.setFocus()
            return

        self.accept()

    @property
    def codigo(self) -> str:
        return self._inp_codigo.text().strip().upper()

    @property
    def nome(self) -> str:
        return self._inp_nome.text().strip()


class ClientesDialog(QDialog):
    """Diálogo completo de gerenciamento de clientes (CRUD).

    Args:
        caminho_planilha: Caminho absoluto para o arquivo .xlsx.
        parent: Widget pai.
    """

    def __init__(self, caminho_planilha: Path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("👥  Gerenciar Clientes — Media Rats Artgen")
        self.setMinimumSize(600, 480)
        self.setStyleSheet(ESTILO_DIALOG)
        self._caminho = Path(caminho_planilha)
        self._writer = ExcelWriter(self._caminho)
        self._build_ui()
        self._carregar_clientes()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 14, 16, 14)

        titulo = QLabel("Clientes Cadastrados")
        titulo.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        titulo.setStyleSheet("color: #E0E0E0;")
        layout.addWidget(titulo)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        self._tabela = QTableWidget(0, 2)
        self._tabela.setHorizontalHeaderLabels(["Código", "Nome do Cliente"])
        self._tabela.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._tabela.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._tabela.verticalHeader().setVisible(False)
        self._tabela.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tabela.setAlternatingRowColors(True)
        self._tabela.setStyleSheet(
            "QTableWidget { alternate-background-color: #1E2A38; }"
        )
        self._tabela.doubleClicked.connect(self._editar_cliente)
        layout.addWidget(self._tabela, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._btn_cadastrar = _btn("➕  Cadastrar Cliente", "#1565C0", "#1976D2")
        self._btn_editar = _btn("✏️  Editar Cliente", "#F57F17", "#F9A825")
        self._btn_remover = _btn("🗑  Remover Cliente", "#C62828", "#D32F2F")
        btn_voltar = _btn("← Voltar", "#263238", "#37474F", "#B0BEC5")

        self._btn_cadastrar.clicked.connect(self._cadastrar_cliente)
        self._btn_editar.clicked.connect(self._editar_cliente)
        self._btn_remover.clicked.connect(self._remover_cliente)
        btn_voltar.clicked.connect(self.accept)

        btn_row.addWidget(self._btn_cadastrar)
        btn_row.addWidget(self._btn_editar)
        btn_row.addWidget(self._btn_remover)
        btn_row.addStretch()
        btn_row.addWidget(btn_voltar)
        layout.addLayout(btn_row)

        self._tabela.selectionModel().selectionChanged.connect(self._atualizar_estado_botoes)
        self._atualizar_estado_botoes()

    def _carregar_clientes(self) -> None:
        """Lê os clientes da planilha e preenche a tabela."""
        try:
            clientes = self._writer.listar_clientes()
        except Exception as exc:
            QMessageBox.critical(self, "Erro", f"Não foi possível carregar clientes:\n{exc}")
            return

        self._tabela.setRowCount(0)
        for cl in clientes:
            row = self._tabela.rowCount()
            self._tabela.insertRow(row)
            item_cod = QTableWidgetItem(cl["codigo"])
            item_cod.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_cod.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            self._tabela.setItem(row, 0, item_cod)
            self._tabela.setItem(row, 1, QTableWidgetItem(cl["nome"]))

        self._tabela.resizeRowsToContents()
        self._atualizar_estado_botoes()

    def _linha_selecionada(self) -> Optional[int]:
        """Retorna o índice da linha selecionada ou None."""
        indices = self._tabela.selectionModel().selectedRows()
        return indices[0].row() if indices else None

    def _dados_linha(self, row: int) -> tuple:
        """Retorna (codigo, nome) da linha indicada.

        Args:
            row: Índice da linha.

        Returns:
            Tupla (codigo, nome).
        """
        codigo = self._tabela.item(row, 0).text()
        nome = self._tabela.item(row, 1).text()
        return codigo, nome

    def _atualizar_estado_botoes(self) -> None:
        """Habilita/desabilita botões de editar e remover conforme seleção."""
        tem_selecao = self._linha_selecionada() is not None
        self._btn_editar.setEnabled(tem_selecao)
        self._btn_remover.setEnabled(tem_selecao)

    def _cadastrar_cliente(self) -> None:
        """Abre formulário para cadastrar um novo cliente."""
        dlg = _ClienteFormDialog("Cadastrar Novo Cliente", parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            self._writer.adicionar_cliente(dlg.codigo, dlg.nome)
            self._carregar_clientes()
            QMessageBox.information(
                self, "Sucesso",
                f"✅ Cliente '{dlg.codigo} — {dlg.nome}' cadastrado com sucesso!"
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Erro ao Cadastrar", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Erro", f"Erro inesperado:\n{exc}")

    def _editar_cliente(self) -> None:
        """Abre formulário para editar o cliente selecionado."""
        row = self._linha_selecionada()
        if row is None:
            QMessageBox.information(self, "Seleção vazia", "Selecione um cliente para editar.")
            return

        codigo_orig, nome_orig = self._dados_linha(row)
        dlg = _ClienteFormDialog(
            "Editar Cliente",
            codigo_inicial=codigo_orig,
            nome_inicial=nome_orig,
            parent=self,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            self._writer.atualizar_cliente(codigo_orig, dlg.codigo, dlg.nome)
            self._carregar_clientes()
            QMessageBox.information(
                self, "Sucesso",
                f"✅ Cliente atualizado para '{dlg.codigo} — {dlg.nome}'."
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Erro ao Editar", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Erro", f"Erro inesperado:\n{exc}")

    def _remover_cliente(self) -> None:
        """Remove o cliente selecionado após confirmação."""
        row = self._linha_selecionada()
        if row is None:
            QMessageBox.information(self, "Seleção vazia", "Selecione um cliente para remover.")
            return

        codigo, nome = self._dados_linha(row)

        resp = QMessageBox.question(
            self,
            "Confirmar Remoção",
            f"Realmente deseja remover o cliente\n\n"
            f"  '{nome}' (código: {codigo})?\n\n"
            "Esta ação não pode ser desfeita.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return

        try:
            self._writer.remover_cliente(codigo)
            self._carregar_clientes()
            QMessageBox.information(
                self, "Removido",
                f"Cliente '{nome}' removido com sucesso."
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Erro ao Remover", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Erro", f"Erro inesperado:\n{exc}")
