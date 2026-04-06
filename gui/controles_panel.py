"""
Painel de controle (botões de ação) do Media Rats - Artgen.
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QIcon


def _btn(texto: str, cor_bg: str, cor_hover: str, cor_texto: str = "#FFFFFF") -> QPushButton:
    """Cria um QPushButton estilizado.

    Args:
        texto: Texto exibido no botão.
        cor_bg: Cor de fundo normal.
        cor_hover: Cor de fundo ao passar o mouse.
        cor_texto: Cor do texto.

    Returns:
        QPushButton configurado.
    """
    b = QPushButton(texto)
    b.setMinimumHeight(36)
    b.setStyleSheet(
        f"QPushButton {{ background-color: {cor_bg}; color: {cor_texto}; "
        f"border: none; border-radius: 6px; padding: 6px 16px; font-size: 12px; font-weight: bold; }}"
        f"QPushButton:hover {{ background-color: {cor_hover}; }}"
        f"QPushButton:disabled {{ background-color: #37474F; color: #607D8B; }}"
        f"QPushButton:pressed {{ background-color: #263238; }}"
    )
    return b


class ControlesPanel(QWidget):
    """Painel inferior com botões de controle da geração."""

    sinal_iniciar = pyqtSignal()
    sinal_pausar = pyqtSignal()
    sinal_cancelar = pyqtSignal()
    sinal_recarregar = pyqtSignal()
    sinal_abrir_output = pyqtSignal()
    sinal_configuracoes = pyqtSignal()
    sinal_clientes = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._pausado = False
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(8)

        self._btn_iniciar = _btn("▶  Iniciar Geração", "#1565C0", "#1976D2")
        self._btn_pausar = _btn("⏸  Pausar", "#F57F17", "#F9A825")
        self._btn_cancelar = _btn("⏹  Cancelar", "#C62828", "#D32F2F")
        self._btn_clientes = _btn("👥  Clientes", "#1B5E20", "#2E7D32")
        self._btn_recarregar = _btn("🔄  Recarregar", "#263238", "#37474F", "#B0BEC5")
        self._btn_output = _btn("📁  Output", "#263238", "#37474F", "#B0BEC5")
        self._btn_config = _btn("⚙  Configurações", "#263238", "#37474F", "#B0BEC5")

        self._btn_iniciar.clicked.connect(self.sinal_iniciar)
        self._btn_pausar.clicked.connect(self._toggle_pausa)
        self._btn_cancelar.clicked.connect(self.sinal_cancelar)
        self._btn_clientes.clicked.connect(self.sinal_clientes)
        self._btn_recarregar.clicked.connect(self.sinal_recarregar)
        self._btn_output.clicked.connect(self.sinal_abrir_output)
        self._btn_config.clicked.connect(self.sinal_configuracoes)

        layout.addWidget(self._btn_iniciar)
        layout.addWidget(self._btn_pausar)
        layout.addWidget(self._btn_cancelar)
        layout.addStretch()
        layout.addWidget(self._btn_clientes)
        layout.addWidget(self._btn_recarregar)
        layout.addWidget(self._btn_output)
        layout.addWidget(self._btn_config)

        self.set_estado_inicial()

    def _toggle_pausa(self) -> None:
        """Alterna entre Pausar e Retomar, emitindo o sinal correspondente."""
        self._pausado = not self._pausado
        if self._pausado:
            self._btn_pausar.setText("▶  Retomar")
            self._btn_pausar.setStyleSheet(
                self._btn_pausar.styleSheet().replace("#F57F17", "#2E7D32").replace("#F9A825", "#388E3C")
            )
        else:
            self._btn_pausar.setText("⏸  Pausar")
            self._btn_pausar.setStyleSheet(
                self._btn_pausar.styleSheet().replace("#2E7D32", "#F57F17").replace("#388E3C", "#F9A825")
            )
        self.sinal_pausar.emit()

    def set_estado_inicial(self) -> None:
        """Configura estado dos botões quando não há geração em andamento."""
        self._btn_iniciar.setEnabled(True)
        self._btn_pausar.setEnabled(False)
        self._btn_cancelar.setEnabled(False)
        self._pausado = False
        self._btn_pausar.setText("⏸  Pausar")

    def set_estado_gerando(self) -> None:
        """Configura estado dos botões durante uma geração ativa."""
        self._btn_iniciar.setEnabled(False)
        self._btn_pausar.setEnabled(True)
        self._btn_cancelar.setEnabled(True)
        self._pausado = False
        self._btn_pausar.setText("⏸  Pausar")

    def set_estado_pausado(self) -> None:
        """Configura estado dos botões quando a geração está pausada."""
        self._btn_iniciar.setEnabled(False)
        self._btn_pausar.setEnabled(True)
        self._btn_cancelar.setEnabled(True)
