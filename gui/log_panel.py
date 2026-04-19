"""
Painel de log em tempo real do Media Rats - Artgen.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QColor, QTextCharFormat, QTextCursor, QFont

MAX_LINHAS_LOG = 500


COR_TIPO = {
    "info":    "#7a7a7a",
    "sucesso": "#00dd00",
    "aviso":   "#FF9800",
    "erro":    "#F44336",
}


class LogPanel(QWidget):
    """Widget que exibe mensagens de log com scroll automático e cores por tipo."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header = QHBoxLayout()
        titulo = QLabel("Log em Tempo Real")
        titulo.setStyleSheet("color: #00cc00; font-weight: bold; font-size: 13px;")
        header.addWidget(titulo)
        header.addStretch()

        btn_limpar = QPushButton("Limpar")
        btn_limpar.setFixedWidth(70)
        btn_limpar.setStyleSheet(
            "QPushButton { background: #111111; color: #555555; border: 1px solid #1a2a1a; "
            "border-radius: 4px; padding: 3px 8px; font-size: 11px; }"
            "QPushButton:hover { background: #002200; color: #00cc00; }"
        )
        btn_limpar.clicked.connect(self._limpar)
        header.addWidget(btn_limpar)
        layout.addLayout(header)

        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setFont(QFont("Consolas", 10))
        self._text_edit.setStyleSheet(
            "QTextEdit { background-color: #000000; color: #c0c0c0; "
            "border: 1px solid #1a3a1a; border-radius: 6px; padding: 8px; }"
        )
        layout.addWidget(self._text_edit)

    @pyqtSlot(str, str)
    def adicionar_mensagem(self, mensagem: str, tipo: str = "info") -> None:
        """Adiciona uma mensagem ao painel de log com a cor correspondente ao tipo.

        Args:
            mensagem: Texto da mensagem (inclui timestamp).
            tipo: Tipo da mensagem ('info', 'sucesso', 'aviso', 'erro').
        """
        cor = COR_TIPO.get(tipo, COR_TIPO["info"])
        cursor = self._text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt = QTextCharFormat()
        fmt.setForeground(QColor(cor))
        cursor.setCharFormat(fmt)
        cursor.insertText(mensagem + "\n")

        doc = self._text_edit.document()
        while doc.blockCount() > MAX_LINHAS_LOG:
            del_cursor = QTextCursor(doc.begin())
            del_cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            del_cursor.removeSelectedText()
            del_cursor.deleteChar()

        self._text_edit.setTextCursor(cursor)
        self._text_edit.ensureCursorVisible()

    def _limpar(self) -> None:
        """Limpa todo o conteúdo do painel de log."""
        self._text_edit.clear()
