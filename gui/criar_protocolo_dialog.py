"""
Diálogo de criação de protocolo do Media Rats - Artgen.

Fluxo:
  1. Usuário escolhe cliente (dropdown alfabético), tema e qtde de artes (1–10).
  2. O diálogo gera dinamicamente os campos de prompt conforme a qtde.
  3. Ao confirmar, persiste a solicitação na planilha e retorna o objeto Solicitacao.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QComboBox, QSpinBox, QPushButton, QMessageBox,
    QScrollArea, QWidget, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from excel.writer import ExcelWriter


_ESTILO = (
    "QDialog { background-color: #000000; color: #d0d0d0; }"
    "QLabel { color: #888888; font-size: 12px; }"
    "QLineEdit { background: #111111; color: #d0d0d0; border: 1px solid #282828; "
    "border-radius: 4px; padding: 5px 8px; }"
    "QLineEdit:focus { border-color: #00aa00; }"
    "QComboBox { background: #111111; color: #d0d0d0; border: 1px solid #282828; "
    "border-radius: 4px; padding: 5px 8px; }"
    "QComboBox::drop-down { border: none; }"
    "QComboBox QAbstractItemView { background: #111111; color: #d0d0d0; "
    "selection-background-color: #002200; selection-color: #00ff00; border: 1px solid #282828; }"
    "QSpinBox { background: #111111; color: #d0d0d0; border: 1px solid #282828; "
    "border-radius: 4px; padding: 5px 8px; }"
    "QSpinBox::up-button, QSpinBox::down-button { background: #1a1a1a; border: none; }"
    "QFrame[frameShape='4'] { color: #1a3a1a; }"
    "QScrollArea { border: none; background: transparent; }"
    "QScrollBar:vertical { background: #0d0d0d; width: 8px; border-radius: 4px; }"
    "QScrollBar::handle:vertical { background: #2a2a2a; border-radius: 4px; }"
    "QScrollBar::handle:vertical:hover { background: #004400; }"
)


def _btn(texto: str, bg: str, hover: str, cor_texto: str = "#FFFFFF") -> QPushButton:
    b = QPushButton(texto)
    b.setMinimumHeight(34)
    b.setStyleSheet(
        f"QPushButton {{ background: {bg}; color: {cor_texto}; border: none; "
        f"border-radius: 5px; padding: 5px 16px; font-size: 12px; font-weight: bold; }}"
        f"QPushButton:hover {{ background: {hover}; }}"
        f"QPushButton:disabled {{ background: #263238; color: #546E7A; }}"
    )
    return b


def _secao(texto: str) -> QLabel:
    lbl = QLabel(texto)
    lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
    lbl.setStyleSheet(
        "color: #00cc00; padding-top: 8px; padding-bottom: 2px; "
        "border-bottom: 1px solid #003300;"
    )
    return lbl


class CriarProtocoloDialog(QDialog):
    """Diálogo para criação de um novo protocolo de geração de artes.

    Exibe campos de cliente (dropdown), tema, quantidade de artes e gera
    dinamicamente os campos de prompt de acordo com a quantidade informada.
    Ao confirmar, persiste a solicitação na planilha via ExcelWriter e
    retorna o objeto Solicitacao criado.

    Args:
        caminho_planilha: Caminho absoluto para o arquivo .xlsx.
        parent: Widget pai.
    """

    MAX_ARTES = 10

    def __init__(self, caminho_planilha: Path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("✚  Criar Protocolo — Media Rats Artgen")
        self.setMinimumSize(520, 560)
        self.resize(560, 620)
        self.setStyleSheet(_ESTILO)

        self._caminho = Path(caminho_planilha)
        self._writer = ExcelWriter(self._caminho)
        self._clientes: list = []
        self._prompts_inputs: List[QLineEdit] = []
        self._solicitacao_criada = None

        self._build_ui()
        self._carregar_clientes()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(18, 14, 18, 14)

        titulo = QLabel("Novo Protocolo de Geração")
        titulo.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        titulo.setStyleSheet("color: #d0d0d0; padding-bottom: 4px;")
        root.addWidget(titulo)

        sep_top = QFrame()
        sep_top.setFrameShape(QFrame.Shape.HLine)
        sep_top.setStyleSheet("color: #1a3a1a;")
        root.addWidget(sep_top)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self._form_layout = QVBoxLayout(container)
        self._form_layout.setSpacing(8)
        self._form_layout.setContentsMargins(2, 4, 8, 4)

        self._form_layout.addWidget(_secao("Dados do Protocolo"))

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._cmb_cliente = QComboBox()
        self._cmb_cliente.setMinimumHeight(32)
        self._cmb_cliente.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        self._inp_tema = QLineEdit()
        self._inp_tema.setPlaceholderText("Ex: Lançamento de coleção verão, Promoção Black Friday...")

        self._spn_qtde = QSpinBox()
        self._spn_qtde.setMinimum(1)
        self._spn_qtde.setMaximum(self.MAX_ARTES)
        self._spn_qtde.setValue(1)
        self._spn_qtde.setMinimumHeight(32)
        self._spn_qtde.setSuffix(f"  (máx. {self.MAX_ARTES})")

        form.addRow("Cliente *:", self._cmb_cliente)
        form.addRow("Tema *:", self._inp_tema)
        form.addRow("Qtde de Artes *:", self._spn_qtde)
        self._form_layout.addLayout(form)

        self._lbl_prompts_secao = _secao("Prompts")
        self._form_layout.addWidget(self._lbl_prompts_secao)

        self._prompts_container = QWidget()
        self._prompts_container.setStyleSheet("background: transparent;")
        self._prompts_form = QFormLayout(self._prompts_container)
        self._prompts_form.setSpacing(8)
        self._prompts_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._form_layout.addWidget(self._prompts_container)

        self._form_layout.addStretch()
        scroll.setWidget(container)
        root.addWidget(scroll, stretch=1)

        sep_bot = QFrame()
        sep_bot.setFrameShape(QFrame.Shape.HLine)
        sep_bot.setStyleSheet("color: #1a3a1a;")
        root.addWidget(sep_bot)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._btn_gerar_prompts = _btn("🔁  Gerar Campos", "#002a00", "#004400", "#00dd00")
        self._btn_criar = _btn("✚  Criar Protocolo", "#004400", "#006600", "#00ff00")
        btn_cancelar = _btn("Cancelar", "#181818", "#222222", "#666666")

        self._btn_gerar_prompts.clicked.connect(self._atualizar_campos_prompts)
        self._btn_criar.clicked.connect(self._validar_e_criar)
        btn_cancelar.clicked.connect(self.reject)

        btn_row.addWidget(self._btn_gerar_prompts)
        btn_row.addStretch()
        btn_row.addWidget(btn_cancelar)
        btn_row.addWidget(self._btn_criar)
        root.addLayout(btn_row)

        self._spn_qtde.valueChanged.connect(self._atualizar_campos_prompts)
        self._atualizar_campos_prompts()

    def _carregar_clientes(self) -> None:
        """Preenche o dropdown de clientes em ordem alfabética."""
        try:
            self._clientes = self._writer.listar_clientes()
        except Exception as exc:
            QMessageBox.critical(
                self, "Erro", f"Não foi possível carregar clientes:\n{exc}"
            )
            self._clientes = []

        self._cmb_cliente.clear()
        if not self._clientes:
            self._cmb_cliente.addItem("— Nenhum cliente cadastrado —")
            self._cmb_cliente.setEnabled(False)
        else:
            for cl in self._clientes:
                self._cmb_cliente.addItem(f"{cl['nome']}  ({cl['codigo']})", userData=cl)

    def _atualizar_campos_prompts(self) -> None:
        """Reconstrói dinamicamente os campos de prompt conforme a quantidade."""
        qtde = self._spn_qtde.value()

        valores_atuais = [inp.text() for inp in self._prompts_inputs]

        while self._prompts_form.rowCount() > 0:
            self._prompts_form.removeRow(0)
        self._prompts_inputs.clear()

        for i in range(1, qtde + 1):
            inp = QLineEdit()
            inp.setPlaceholderText(
                f"Descreva a arte {i}: estilo, composição, elemento principal..."
            )
            inp.setMinimumHeight(30)
            valor_anterior = valores_atuais[i - 1] if i - 1 < len(valores_atuais) else ""
            inp.setText(valor_anterior)
            lbl = QLabel(f"Prompt {i}:")
            lbl.setStyleSheet(
                "color: #00cc00; font-size: 12px; font-weight: bold;"
                if i == 1 else "color: #446644; font-size: 12px;"
            )
            self._prompts_form.addRow(lbl, inp)
            self._prompts_inputs.append(inp)

    # ------------------------------------------------------------------
    # Validação e criação
    # ------------------------------------------------------------------

    def _validar_e_criar(self) -> None:
        """Valida todos os campos e persiste o protocolo se tudo estiver OK."""
        if not self._clientes or not self._cmb_cliente.isEnabled():
            QMessageBox.warning(
                self, "Sem clientes",
                "Não há clientes cadastrados. Cadastre um cliente antes de criar um protocolo."
            )
            return

        idx = self._cmb_cliente.currentIndex()
        if idx < 0 or idx >= len(self._clientes):
            QMessageBox.warning(self, "Cliente obrigatório", "Selecione um cliente.")
            self._cmb_cliente.setFocus()
            return

        cliente_dados = self._clientes[idx]

        tema = self._inp_tema.text().strip()
        if not tema:
            QMessageBox.warning(self, "Tema obrigatório", "Preencha o tema do protocolo.")
            self._inp_tema.setFocus()
            return

        qtde = self._spn_qtde.value()
        if not (1 <= qtde <= self.MAX_ARTES):
            QMessageBox.warning(
                self, "Quantidade inválida",
                f"A quantidade de artes deve ser entre 1 e {self.MAX_ARTES}."
            )
            self._spn_qtde.setFocus()
            return

        prompts: List[str] = []
        for i, inp in enumerate(self._prompts_inputs, start=1):
            val = inp.text().strip()
            if not val:
                QMessageBox.warning(
                    self, f"Prompt {i} obrigatório",
                    f"O campo 'Prompt {i}' está vazio.\n"
                    f"Preencha todos os {qtde} prompts antes de criar o protocolo."
                )
                inp.setFocus()
                return
            prompts.append(val)

        try:
            sol = self._writer.adicionar_solicitacao(
                codigo_cliente=cliente_dados["codigo"],
                nome_cliente=cliente_dados["nome"],
                tema=tema,
                prompts=prompts,
                status="Planejado",
            )
            self._solicitacao_criada = sol
            QMessageBox.information(
                self, "Protocolo Criado",
                f"✅ Protocolo '{sol.protocolo}' criado com sucesso!\n\n"
                f"Cliente: {sol.cliente}\n"
                f"Tema: {sol.tema}\n"
                f"Artes: {len([p for p in sol.prompts if p])}"
            )
            self.accept()

        except Exception as exc:
            QMessageBox.critical(
                self, "Erro ao Criar Protocolo",
                f"Não foi possível salvar o protocolo:\n{exc}"
            )

    # ------------------------------------------------------------------
    # Resultado
    # ------------------------------------------------------------------

    @property
    def solicitacao(self):
        """Retorna o objeto Solicitacao criado, ou None se cancelado."""
        return self._solicitacao_criada
