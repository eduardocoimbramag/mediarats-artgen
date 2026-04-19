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
        f"QPushButton:disabled {{ background-color: #111111; color: #333333; }}"
        f"QPushButton:pressed {{ background-color: #000000; }}"
    )
    return b


class ControlesPanel(QWidget):
    """Painel inferior com botões de controle da geração."""

    sinal_iniciar = pyqtSignal()
    sinal_processar_fila = pyqtSignal()
    sinal_pausar = pyqtSignal()
    sinal_cancelar = pyqtSignal()
    sinal_recarregar = pyqtSignal()
    sinal_abrir_output = pyqtSignal()
    sinal_configuracoes = pyqtSignal()
    sinal_clientes = pyqtSignal()
    sinal_criar_protocolo = pyqtSignal()
    sinal_remover_protocolo = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._pausado = False
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(8)

        self._btn_iniciar = _btn("▶  Iniciar Geração", "#004400", "#006600", "#00ff00")
        self._btn_processar_fila = _btn("▶▶  Processar Fila", "#002a44", "#003a66", "#44aaff")
        self._btn_pausar = _btn("⏸  Pausar", "#F57F17", "#F9A825")
        self._btn_cancelar = _btn("⏹  Cancelar", "#C62828", "#D32F2F")
        self._btn_remover_protocolo = _btn("🗑  Remover Protocolo", "#B71C1C", "#C62828")
        self._btn_criar_protocolo = _btn("✚  Criar Protocolo", "#002a00", "#004400", "#00dd00")
        self._btn_clientes = _btn("👥  Clientes", "#002a00", "#004400", "#00dd00")
        self._btn_recarregar = _btn("🔄  Recarregar", "#181818", "#222222", "#666666")
        self._btn_output = _btn("📁  Output", "#181818", "#222222", "#666666")
        self._btn_config = _btn("⚙  Configurações", "#181818", "#222222", "#666666")

        self._btn_iniciar.clicked.connect(self.sinal_iniciar)
        self._btn_processar_fila.clicked.connect(self.sinal_processar_fila)
        self._btn_pausar.clicked.connect(self._toggle_pausa)
        self._btn_cancelar.clicked.connect(self.sinal_cancelar)
        self._btn_remover_protocolo.clicked.connect(self.sinal_remover_protocolo)
        self._btn_criar_protocolo.clicked.connect(self.sinal_criar_protocolo)
        self._btn_clientes.clicked.connect(self.sinal_clientes)
        self._btn_recarregar.clicked.connect(self.sinal_recarregar)
        self._btn_output.clicked.connect(self.sinal_abrir_output)
        self._btn_config.clicked.connect(self.sinal_configuracoes)

        layout.addWidget(self._btn_iniciar)
        layout.addWidget(self._btn_processar_fila)
        layout.addWidget(self._btn_pausar)
        layout.addWidget(self._btn_cancelar)
        layout.addWidget(self._btn_remover_protocolo)
        layout.addStretch()
        layout.addWidget(self._btn_criar_protocolo)
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
                self._btn_pausar.styleSheet().replace("#F57F17", "#004400").replace("#F9A825", "#006600")
            )
        else:
            self._btn_pausar.setText("⏸  Pausar")
            self._btn_pausar.setStyleSheet(
                self._btn_pausar.styleSheet().replace("#004400", "#F57F17").replace("#006600", "#F9A825")
            )
        self.sinal_pausar.emit()

    def set_estado_inicial(self) -> None:
        """Configura estado dos botões quando não há geração em andamento."""
        self._btn_iniciar.setEnabled(True)
        self._btn_processar_fila.setEnabled(True)
        self._btn_pausar.setEnabled(False)
        self._btn_cancelar.setEnabled(False)
        self._pausado = False
        self._btn_pausar.setText("⏸  Pausar")

    def set_estado_gerando(self) -> None:
        """Configura estado dos botões durante uma geração ativa."""
        self._btn_iniciar.setEnabled(False)
        self._btn_processar_fila.setEnabled(False)
        self._btn_pausar.setEnabled(True)
        self._btn_cancelar.setEnabled(True)
        self._pausado = False
        self._btn_pausar.setText("⏸  Pausar")

    def set_estado_pausado(self) -> None:
        """Configura estado dos botões quando a geração está pausada."""
        self._btn_iniciar.setEnabled(False)
        self._btn_processar_fila.setEnabled(False)
        self._btn_pausar.setEnabled(True)
        self._btn_cancelar.setEnabled(True)
