"""
Painel superior (dashboard) do Media Rats - Artgen.
Exibe informações em tempo real: cliente, protocolo, tema e progresso.
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QProgressBar, QFrame
)
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QFont


class InfoCard(QFrame):
    """Cartão de informação individual do dashboard.

    Args:
        titulo: Título do cartão.
        valor_inicial: Valor inicial exibido.
    """

    def __init__(self, titulo: str, valor_inicial: str = "—", parent=None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "QFrame { background-color: #1E2A38; border: 1px solid #2D3F50; "
            "border-radius: 8px; padding: 8px; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        self._lbl_titulo = QLabel(titulo)
        self._lbl_titulo.setStyleSheet("color: #607D8B; font-size: 10px; font-weight: bold;")
        self._lbl_titulo.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self._lbl_valor = QLabel(valor_inicial)
        self._lbl_valor.setStyleSheet("color: #E0E0E0; font-size: 14px; font-weight: bold;")
        self._lbl_valor.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._lbl_valor.setWordWrap(True)

        layout.addWidget(self._lbl_titulo)
        layout.addWidget(self._lbl_valor)

    def definir_valor(self, valor: str) -> None:
        """Atualiza o valor exibido no cartão.

        Args:
            valor: Novo texto a exibir.
        """
        self._lbl_valor.setText(valor)


class DashboardPanel(QWidget):
    """Painel superior com informações em tempo real da geração atual."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(130)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(6)

        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(10)

        self._card_cliente = InfoCard("CLIENTE ATUAL")
        self._card_protocolo = InfoCard("PROTOCOLO")
        self._card_tema = InfoCard("TEMA")
        self._card_progresso_label = InfoCard("PROGRESSO")

        for card in [self._card_cliente, self._card_protocolo, self._card_tema, self._card_progresso_label]:
            cards_layout.addWidget(card)

        layout.addLayout(cards_layout)

        progress_container = QWidget()
        progress_layout = QHBoxLayout(progress_container)
        progress_layout.setContentsMargins(0, 0, 0, 0)

        lbl_prog = QLabel("Progresso Geral:")
        lbl_prog.setStyleSheet("color: #607D8B; font-size: 10px;")
        lbl_prog.setFixedWidth(110)

        self._progress_bar = QProgressBar()
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFormat("%p% (%v/%m artes)")
        self._progress_bar.setFixedHeight(18)
        self._progress_bar.setStyleSheet(
            "QProgressBar { border: 1px solid #2D3F50; border-radius: 4px; "
            "background-color: #1A2332; text-align: center; color: #B0BEC5; font-size: 10px; }"
            "QProgressBar::chunk { background-color: #1565C0; border-radius: 3px; }"
        )

        progress_layout.addWidget(lbl_prog)
        progress_layout.addWidget(self._progress_bar)
        layout.addWidget(progress_container)

    @pyqtSlot(str, str, str)
    def atualizar_info(self, cliente: str, protocolo: str, tema: str) -> None:
        """Atualiza as informações exibidas nos cartões.

        Args:
            cliente: Nome do cliente.
            protocolo: Protocolo da solicitação (ex: DUDE#1).
            tema: Tema da solicitação.
        """
        self._card_cliente.definir_valor(cliente)
        self._card_protocolo.definir_valor(protocolo)
        self._card_tema.definir_valor(tema)

    @pyqtSlot(int, int)
    def atualizar_progresso(self, atual: int, total: int) -> None:
        """Atualiza a barra de progresso.

        Args:
            atual: Número de artes concluídas.
            total: Total de artes a gerar.
        """
        if total > 0:
            self._progress_bar.setMaximum(total)
            self._progress_bar.setValue(atual)
            self._card_progresso_label.definir_valor(f"{atual}/{total} artes")
        else:
            self._progress_bar.setValue(0)
            self._card_progresso_label.definir_valor("—")

    def resetar(self) -> None:
        """Reseta todas as informações do dashboard para o estado inicial."""
        self._card_cliente.definir_valor("—")
        self._card_protocolo.definir_valor("—")
        self._card_tema.definir_valor("—")
        self._card_progresso_label.definir_valor("—")
        self._progress_bar.setValue(0)
        self._progress_bar.setMaximum(10)
