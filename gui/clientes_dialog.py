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
    QFrame, QScrollArea, QSizePolicy
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
    "QScrollArea { border: none; background: transparent; }"
    "QScrollBar:vertical { background: #1A1A2E; width: 8px; }"
    "QScrollBar::handle:vertical { background: #37474F; border-radius: 4px; }"
)

_CODIGO_RE = re.compile(r"^[A-Za-z]{2,6}$")
_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _validar_hex(valor: str) -> bool:
    """Retorna True se o valor for vazio ou um HEX válido (#RRGGBB).

    Args:
        valor: String a validar.

    Returns:
        True se válido.
    """
    v = valor.strip()
    return v == "" or bool(_HEX_RE.match(v))


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


def _secao(texto: str) -> QLabel:
    """Cria um label de seção com estilo de destaque.

    Args:
        texto: Texto da seção.

    Returns:
        QLabel estilizado.
    """
    lbl = QLabel(texto)
    lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
    lbl.setStyleSheet(
        "color: #90CAF9; padding-top: 8px; padding-bottom: 2px; "
        "border-bottom: 1px solid #1565C0;"
    )
    return lbl


class _ClienteFormDialog(QDialog):
    """Diálogo interno para cadastrar ou editar um cliente.

    Inclui campos básicos (código, nome) e os campos estratégicos
    de criação de prompts (nicho, descrição, público-alvo, etc.).

    Args:
        titulo: Título da janela.
        dados_iniciais: Dict com valores iniciais de todos os campos.
        codigo_fixo: Se True, o campo de código fica somente-leitura.
        parent: Widget pai.
    """

    def __init__(
        self,
        titulo: str,
        dados_iniciais: Optional[dict] = None,
        codigo_fixo: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.setMinimumSize(480, 580)
        self.resize(520, 640)
        self.setStyleSheet(ESTILO_DIALOG)
        dados = dados_iniciais or {}
        self._build_ui(dados, codigo_fixo)

    def _build_ui(self, dados: dict, codigo_fixo: bool) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(16, 14, 16, 14)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        form_layout = QVBoxLayout(container)
        form_layout.setSpacing(6)
        form_layout.setContentsMargins(4, 4, 8, 4)

        form_layout.addWidget(_secao("Identificação"))
        form_id = QFormLayout()
        form_id.setSpacing(8)
        form_id.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._inp_codigo = QLineEdit(dados.get("codigo", ""))
        self._inp_codigo.setPlaceholderText("Ex: DUDE (2-6 letras)")
        self._inp_codigo.setMaxLength(6)
        if codigo_fixo:
            self._inp_codigo.setReadOnly(True)
            self._inp_codigo.setStyleSheet(
                "QLineEdit { background: #263238; color: #78909C; border: 1px solid #37474F; "
                "border-radius: 4px; padding: 5px 8px; }"
            )

        self._inp_nome = QLineEdit(dados.get("nome", ""))
        self._inp_nome.setPlaceholderText("Nome completo da empresa")

        form_id.addRow("Código *:", self._inp_codigo)
        form_id.addRow("Nome *:", self._inp_nome)
        form_layout.addLayout(form_id)

        form_layout.addWidget(_secao("Identidade de Marca"))
        form_marca = QFormLayout()
        form_marca.setSpacing(8)
        form_marca.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._inp_nicho = QLineEdit(dados.get("nicho", ""))
        self._inp_nicho.setPlaceholderText("Ex: Moda, Gastronomia, Tech...")

        self._inp_descricao = QLineEdit(dados.get("descricao", ""))
        self._inp_descricao.setPlaceholderText("Breve descrição da empresa")

        self._inp_publico = QLineEdit(dados.get("publico_alvo", ""))
        self._inp_publico.setPlaceholderText("Ex: Jovens 18-30 anos, consumidores de moda")

        self._inp_formalidade = QLineEdit(dados.get("formalidade", ""))
        self._inp_formalidade.setPlaceholderText("Ex: Formal, Casual, Técnico, Descontraído")

        form_marca.addRow("Nicho:", self._inp_nicho)
        form_marca.addRow("Descrição:", self._inp_descricao)
        form_marca.addRow("Público-Alvo:", self._inp_publico)
        form_marca.addRow("Formalidade:", self._inp_formalidade)
        form_layout.addLayout(form_marca)

        form_layout.addWidget(_secao("Estilo Visual"))
        form_estilo = QFormLayout()
        form_estilo.setSpacing(8)
        form_estilo.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._inp_estilo_visual = QLineEdit(dados.get("estilo_visual", ""))
        self._inp_estilo_visual.setPlaceholderText("Ex: Minimalista, Bold, Luxo, Street")

        self._inp_estilo_foto = QLineEdit(dados.get("estilo_foto", ""))
        self._inp_estilo_foto.setPlaceholderText("Ex: Editorial, Lifestyle, Product Shot")

        form_estilo.addRow("Estilo Visual:", self._inp_estilo_visual)
        form_estilo.addRow("Estilo Fotográfico:", self._inp_estilo_foto)
        form_layout.addLayout(form_estilo)

        form_layout.addWidget(_secao("Paleta de Cores"))
        form_cores = QFormLayout()
        form_cores.setSpacing(8)
        form_cores.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        lbl_hex = QLabel("Formato: #RRGGBB  (ex: #1565C0)")
        lbl_hex.setStyleSheet("color: #546E7A; font-size: 11px; padding-bottom: 2px;")
        form_layout.addWidget(lbl_hex)

        self._inp_cor_primaria = QLineEdit(dados.get("cor_primaria", ""))
        self._inp_cor_primaria.setPlaceholderText("#000000")
        self._inp_cor_primaria.setMaxLength(7)
        self._inp_cor_primaria.textChanged.connect(
            lambda t: self._aplicar_preview_cor(self._inp_cor_primaria, t)
        )

        self._inp_cor_secundaria = QLineEdit(dados.get("cor_secundaria", ""))
        self._inp_cor_secundaria.setPlaceholderText("#FFFFFF")
        self._inp_cor_secundaria.setMaxLength(7)
        self._inp_cor_secundaria.textChanged.connect(
            lambda t: self._aplicar_preview_cor(self._inp_cor_secundaria, t)
        )

        self._inp_cor_fundo = QLineEdit(dados.get("cor_fundo", ""))
        self._inp_cor_fundo.setPlaceholderText("#F5F5F5")
        self._inp_cor_fundo.setMaxLength(7)
        self._inp_cor_fundo.textChanged.connect(
            lambda t: self._aplicar_preview_cor(self._inp_cor_fundo, t)
        )

        form_cores.addRow("Cor Primária:", self._inp_cor_primaria)
        form_cores.addRow("Cor Secundária:", self._inp_cor_secundaria)
        form_cores.addRow("Cor de Fundo:", self._inp_cor_fundo)
        form_layout.addLayout(form_cores)

        form_layout.addStretch()
        scroll.setWidget(container)
        root.addWidget(scroll, stretch=1)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #30363D;")
        root.addWidget(sep)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_salvar = _btn("💾  Salvar", "#1565C0", "#1976D2")
        btn_cancelar = _btn("Cancelar", "#263238", "#37474F", "#B0BEC5")
        btn_salvar.clicked.connect(self._validar_e_aceitar)
        btn_cancelar.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(btn_cancelar)
        btn_row.addWidget(btn_salvar)
        root.addLayout(btn_row)

        for inp in (self._inp_cor_primaria, self._inp_cor_secundaria, self._inp_cor_fundo):
            self._aplicar_preview_cor(inp, inp.text())

    def _aplicar_preview_cor(self, campo: QLineEdit, texto: str) -> None:
        """Muda a borda do campo de cor para feedback visual do HEX.

        Args:
            campo: Campo de cor.
            texto: Valor atual.
        """
        t = texto.strip()
        if t == "":
            campo.setStyleSheet("")
        elif _HEX_RE.match(t):
            campo.setStyleSheet(
                f"QLineEdit {{ background: #1E2A38; color: #E0E0E0; "
                f"border: 2px solid {t}; border-radius: 4px; padding: 5px 8px; }}"
            )
        else:
            campo.setStyleSheet(
                "QLineEdit { background: #1E2A38; color: #E0E0E0; "
                "border: 2px solid #C62828; border-radius: 4px; padding: 5px 8px; }"
            )

    def _validar_e_aceitar(self) -> None:
        """Valida todos os campos e fecha com accept se estiver OK."""
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

        campos_cor = [
            ("Cor Primária", self._inp_cor_primaria),
            ("Cor Secundária", self._inp_cor_secundaria),
            ("Cor de Fundo", self._inp_cor_fundo),
        ]
        for label, campo in campos_cor:
            if not _validar_hex(campo.text()):
                QMessageBox.warning(
                    self, f"{label} inválida",
                    f"O campo '{label}' deve estar no formato HEX: #RRGGBB\n"
                    f"Exemplo: #1565C0\nOu deixe em branco para ignorar."
                )
                campo.setFocus()
                return

        self.accept()

    @property
    def codigo(self) -> str:
        return self._inp_codigo.text().strip().upper()

    @property
    def nome(self) -> str:
        return self._inp_nome.text().strip()

    @property
    def dados(self) -> dict:
        """Retorna todos os campos como dicionário."""
        return {
            "codigo": self.codigo,
            "nome": self.nome,
            "nicho": self._inp_nicho.text().strip(),
            "descricao": self._inp_descricao.text().strip(),
            "publico_alvo": self._inp_publico.text().strip(),
            "formalidade": self._inp_formalidade.text().strip(),
            "estilo_visual": self._inp_estilo_visual.text().strip(),
            "estilo_foto": self._inp_estilo_foto.text().strip(),
            "cor_primaria": self._inp_cor_primaria.text().strip(),
            "cor_secundaria": self._inp_cor_secundaria.text().strip(),
            "cor_fundo": self._inp_cor_fundo.text().strip(),
        }


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

        self._tabela = QTableWidget(0, 3)
        self._tabela.setHorizontalHeaderLabels(["Código", "Nome do Cliente", "Nicho"])
        self._tabela.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._tabela.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._tabela.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
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
        """Lê os clientes da planilha e preenche a tabela (ordem alfabética)."""
        try:
            clientes = self._writer.listar_clientes()
        except Exception as exc:
            QMessageBox.critical(self, "Erro", f"Não foi possível carregar clientes:\n{exc}")
            return

        self._clientes_cache = clientes
        self._tabela.setRowCount(0)
        for cl in clientes:
            row = self._tabela.rowCount()
            self._tabela.insertRow(row)
            item_cod = QTableWidgetItem(cl["codigo"])
            item_cod.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_cod.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            self._tabela.setItem(row, 0, item_cod)
            self._tabela.setItem(row, 1, QTableWidgetItem(cl["nome"]))
            nicho = cl.get("nicho", "")
            self._tabela.setItem(row, 2, QTableWidgetItem(nicho))

        self._tabela.resizeRowsToContents()
        self._atualizar_estado_botoes()

    def _linha_selecionada(self) -> Optional[int]:
        """Retorna o índice da linha selecionada ou None."""
        indices = self._tabela.selectionModel().selectedRows()
        return indices[0].row() if indices else None

    def _dados_linha(self, row: int) -> dict:
        """Retorna todos os dados do cliente na linha indicada.

        Args:
            row: Índice da linha na tabela.

        Returns:
            Dict com todos os campos do cliente (do cache).
        """
        if hasattr(self, "_clientes_cache") and row < len(self._clientes_cache):
            return self._clientes_cache[row]
        return {"codigo": self._tabela.item(row, 0).text(),
                "nome": self._tabela.item(row, 1).text()}

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

        d = dlg.dados
        try:
            self._writer.adicionar_cliente(
                d["codigo"], d["nome"], d["nicho"], d["descricao"],
                d["publico_alvo"], d["formalidade"], d["estilo_visual"],
                d["estilo_foto"], d["cor_primaria"], d["cor_secundaria"], d["cor_fundo"],
            )
            self._carregar_clientes()
            QMessageBox.information(
                self, "Sucesso",
                f"✅ Cliente '{d['codigo']} — {d['nome']}' cadastrado com sucesso!"
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

        dados_orig = self._dados_linha(row)
        codigo_orig = dados_orig.get("codigo", "")

        dlg = _ClienteFormDialog(
            "Editar Cliente",
            dados_iniciais=dados_orig,
            codigo_fixo=False,
            parent=self,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        d = dlg.dados
        try:
            self._writer.atualizar_cliente(
                codigo_orig, d["codigo"], d["nome"], d["nicho"], d["descricao"],
                d["publico_alvo"], d["formalidade"], d["estilo_visual"],
                d["estilo_foto"], d["cor_primaria"], d["cor_secundaria"], d["cor_fundo"],
            )
            self._carregar_clientes()
            QMessageBox.information(
                self, "Sucesso",
                f"✅ Cliente atualizado para '{d['codigo']} — {d['nome']}'."
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

        dados = self._dados_linha(row)
        codigo = dados.get("codigo", "")
        nome = dados.get("nome", codigo)

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
