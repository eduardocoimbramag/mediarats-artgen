"""
Diálogo de configurações do Media Rats - Artgen.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QSpinBox, QCheckBox, QDialogButtonBox,
    QPushButton, QFileDialog, QFrame, QTabWidget, QWidget,
    QMessageBox, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon

from utils.config import Config


ESTILO_INPUT = (
    "QLineEdit, QSpinBox { background-color: #111111; color: #d0d0d0; "
    "border: 1px solid #282828; border-radius: 4px; padding: 5px 8px; }"
    "QLineEdit:focus, QSpinBox:focus { border-color: #00aa00; }"
)

ESTILO_LABEL = "QLabel { color: #888888; font-size: 12px; }"

ESTILO_CHECK = (
    "QCheckBox { color: #d0d0d0; font-size: 12px; spacing: 8px; }"
    "QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #282828; "
    "border-radius: 3px; background: #111111; }"
    "QCheckBox::indicator:checked { background: #004400; border-color: #00aa00; }"
)

ESTILO_BTN_SECUNDARIO = (
    "QPushButton { background: #181818; color: #666666; border: 1px solid #1a2a1a; "
    "border-radius: 4px; padding: 5px 12px; font-size: 11px; }"
    "QPushButton:hover { background: #002200; color: #00cc00; }"
)


class ConfiguracoesDialog(QDialog):
    """Diálogo para editar as configurações do programa."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("⚙  Configurações — Media Rats Artgen")
        self.setMinimumSize(540, 440)
        self.setStyleSheet(
            "QDialog { background-color: #000000; color: #d0d0d0; }"
            "QTabWidget::pane { border: 1px solid #1a3a1a; border-radius: 6px; background: #0d0d0d; }"
            "QTabBar::tab { background: #111111; color: #555555; padding: 8px 18px; border-radius: 4px 4px 0 0; }"
            "QTabBar::tab:selected { background: #003300; color: #00ff00; }"
            "QTabBar::tab:hover:!selected { background: #1a1a1a; color: #888888; }"
        )
        self._build_ui()
        self._carregar_valores()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._tab_geral(), "🗂  Geral")
        self._tabs.addTab(self._tab_navegador(), "🌐  Navegador")
        self._tabs.addTab(self._tab_login(), "🔑  Login")
        layout.addWidget(self._tabs)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._salvar)
        btns.rejected.connect(self.reject)
        btns.setStyleSheet(
            "QPushButton { background: #004400; color: #00ff00; border: none; "
            "border-radius: 4px; padding: 6px 20px; font-size: 12px; font-weight: bold; }"
            "QPushButton:hover { background: #005500; }"
            "QPushButton[text='Cancel'] { background: #181818; color: #888888; border: 1px solid #282828; }"
            "QPushButton[text='Cancel']:hover { background: #222222; color: #aaaaaa; }"
        )
        layout.addWidget(btns)

    def _tab_geral(self) -> QWidget:
        """Cria a aba de configurações gerais.

        Returns:
            Widget da aba Geral.
        """
        tab = QWidget()
        form = QFormLayout(tab)
        form.setSpacing(12)
        form.setContentsMargins(16, 16, 16, 16)

        self._inp_planilha = QLineEdit()
        self._inp_planilha.setStyleSheet(ESTILO_INPUT)

        btn_browse = QPushButton("...")
        btn_browse.setFixedWidth(32)
        btn_browse.setStyleSheet(ESTILO_BTN_SECUNDARIO)
        btn_browse.clicked.connect(self._browse_planilha)

        planilha_row = QHBoxLayout()
        planilha_row.setSpacing(4)
        planilha_row.addWidget(self._inp_planilha)
        planilha_row.addWidget(btn_browse)

        self._inp_output = QLineEdit()
        self._inp_output.setStyleSheet(ESTILO_INPUT)

        self._inp_url = QLineEdit()
        self._inp_url.setStyleSheet(ESTILO_INPUT)
        self._inp_url.setPlaceholderText("https://www.adapta.org")

        form.addRow(_lbl("Caminho da Planilha:", ESTILO_LABEL), planilha_row)
        form.addRow(_lbl("Pasta de Output:", ESTILO_LABEL), self._inp_output)
        form.addRow(_lbl("URL do Adapta.org:", ESTILO_LABEL), self._inp_url)

        return tab

    def _tab_navegador(self) -> QWidget:
        """Cria a aba de configurações do navegador.

        Returns:
            Widget da aba Navegador.
        """
        tab = QWidget()
        form = QFormLayout(tab)
        form.setSpacing(12)
        form.setContentsMargins(16, 16, 16, 16)

        self._spin_timeout = QSpinBox()
        self._spin_timeout.setRange(10, 300)
        self._spin_timeout.setSuffix(" segundos")
        self._spin_timeout.setStyleSheet(ESTILO_INPUT)

        self._chk_headless = QCheckBox("Executar em segundo plano (headless)")
        self._chk_headless.setStyleSheet(ESTILO_CHECK)

        self._chk_fechar = QCheckBox("Fechar navegador após conclusão")
        self._chk_fechar.setStyleSheet(ESTILO_CHECK)

        form.addRow(_lbl("Timeout de geração:", ESTILO_LABEL), self._spin_timeout)
        form.addRow("", self._chk_headless)
        form.addRow("", self._chk_fechar)

        return tab

    def _tab_login(self) -> QWidget:
        """Cria a aba de credenciais de login do Adapta.org.

        Returns:
            Widget da aba Login.
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        aviso = QLabel(
            "ℹ  As credenciais são usadas para login automático no Adapta.org.\n"
            "   São salvas localmente no arquivo .env do projeto."
        )
        aviso.setStyleSheet(
            "QLabel { color: #00aa00; font-size: 11px; background: #001a00; "
            "border: 1px solid #1a3a1a; border-radius: 6px; padding: 8px; }"
        )
        aviso.setWordWrap(True)
        layout.addWidget(aviso)

        form = QFormLayout()
        form.setSpacing(12)

        self._inp_email = QLineEdit()
        self._inp_email.setStyleSheet(ESTILO_INPUT)
        self._inp_email.setPlaceholderText("seu@email.com")

        senha_row = QHBoxLayout()
        senha_row.setSpacing(4)
        self._inp_senha = QLineEdit()
        self._inp_senha.setStyleSheet(ESTILO_INPUT)
        self._inp_senha.setEchoMode(QLineEdit.EchoMode.Password)
        self._inp_senha.setPlaceholderText("••••••••")

        self._btn_olho = QPushButton("👁")
        self._btn_olho.setFixedSize(34, 34)
        self._btn_olho.setCheckable(True)
        self._btn_olho.setStyleSheet(
            "QPushButton { background: #181818; color: #666666; border: 1px solid #282828; "
            "border-radius: 4px; font-size: 14px; }"
            "QPushButton:hover { background: #002200; color: #00cc00; }"
            "QPushButton:checked { background: #003300; color: #00ff00; border-color: #00aa00; }"
        )
        self._btn_olho.toggled.connect(self._toggle_senha_visivel)

        senha_row.addWidget(self._inp_senha)
        senha_row.addWidget(self._btn_olho)

        form.addRow(_lbl("E-mail:", ESTILO_LABEL), self._inp_email)
        form.addRow(_lbl("Senha:", ESTILO_LABEL), senha_row)
        layout.addLayout(form)

        btn_alterar = QPushButton("🔄  Alterar Login")
        btn_alterar.setMinimumHeight(36)
        btn_alterar.setStyleSheet(
            "QPushButton { background: #003300; color: #00dd00; border: none; "
            "border-radius: 6px; padding: 6px 20px; font-size: 12px; font-weight: bold; }"
            "QPushButton:hover { background: #004400; color: #00ff00; }"
            "QPushButton:pressed { background: #002200; }"
        )
        btn_alterar.clicked.connect(self._alterar_login)
        layout.addWidget(btn_alterar)

        layout.addStretch()
        return tab

    def _toggle_senha_visivel(self, visivel: bool) -> None:
        """Alterna a visibilidade do campo de senha.

        Args:
            visivel: True para mostrar, False para ocultar.
        """
        if visivel:
            self._inp_senha.setEchoMode(QLineEdit.EchoMode.Normal)
            self._btn_olho.setText("🙈")
        else:
            self._inp_senha.setEchoMode(QLineEdit.EchoMode.Password)
            self._btn_olho.setText("👁")

    def _alterar_login(self) -> None:
        """Salva apenas as credenciais de login sem fechar o diálogo."""
        email = self._inp_email.text().strip()
        senha = self._inp_senha.text()
        Config.salvar_env({"ADAPTA_EMAIL": email, "ADAPTA_SENHA": senha})
        QMessageBox.information(
            self,
            "Login Atualizado",
            "✅ Credenciais de login salvas com sucesso!\n\n"
            "O login automático será tentado na próxima geração.",
        )

    def _carregar_valores(self) -> None:
        """Preenche os campos com os valores atuais de configuração."""
        self._inp_planilha.setText(Config.CAMINHO_PLANILHA)
        self._inp_output.setText(Config.CAMINHO_OUTPUT)
        self._inp_url.setText(Config.URL_ADAPTA)
        self._spin_timeout.setValue(Config.TIMEOUT_GERADOR)
        self._chk_headless.setChecked(Config.MODO_HEADLESS)
        self._chk_fechar.setChecked(Config.FECHAR_NAVEGADOR_APOS_CONCLUSAO)
        self._inp_email.setText(Config.ADAPTA_EMAIL)
        self._inp_senha.setText(Config.ADAPTA_SENHA)

    def _salvar(self) -> None:
        """Valida e persiste todas as configurações no arquivo .env."""
        dados = {
            "URL_ADAPTA": self._inp_url.text().strip() or "https://www.adapta.org",
            "CAMINHO_PLANILHA": self._inp_planilha.text().strip(),
            "CAMINHO_OUTPUT": self._inp_output.text().strip(),
            "TIMEOUT_GERADOR": str(self._spin_timeout.value()),
            "MODO_HEADLESS": "true" if self._chk_headless.isChecked() else "false",
            "FECHAR_NAVEGADOR_APOS_CONCLUSAO": "true" if self._chk_fechar.isChecked() else "false",
            "IDIOMA_LOG": "pt-BR",
            "ADAPTA_EMAIL": self._inp_email.text().strip(),
            "ADAPTA_SENHA": self._inp_senha.text(),
        }
        Config.salvar_env(dados)
        self.accept()

    def _browse_planilha(self) -> None:
        """Abre diálogo para selecionar o arquivo de planilha."""
        caminho, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Planilha",
            str(Path(Config.CAMINHO_PLANILHA).parent),
            "Excel Files (*.xlsx *.xls)",
        )
        if caminho:
            self._inp_planilha.setText(caminho)


def _lbl(texto: str, estilo: str) -> QLabel:
    """Cria um QLabel estilizado.

    Args:
        texto: Texto do label.
        estilo: Folha de estilo CSS.

    Returns:
        QLabel configurado.
    """
    l = QLabel(texto)
    l.setStyleSheet(estilo)
    return l
