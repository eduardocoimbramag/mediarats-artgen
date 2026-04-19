"""
Diálogo de preview das imagens geradas.
Exibe thumbnails das artes após a conclusão de uma geração.
"""

from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path
from typing import List

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QWidget, QPushButton
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QFont

from gui.theme import (
    FUNDO_PRINCIPAL, FUNDO_CARD, VERDE_BORDA, VERDE_BORDA_SUTIL,
    VERDE_PRIMARIO, VERDE_MEDIO, VERDE_ESCURO, TEXTO_MUTED, estilo_dialog,
)

THUMB_SIZE = 190


class PreviewDialog(QDialog):
    """Exibe thumbnails das imagens geradas após a conclusão da geração.

    Args:
        caminhos: Lista de caminhos absolutos das imagens geradas.
        protocolo: Protocolo da solicitação (para o título da janela).
    """

    def __init__(
        self,
        caminhos: List[str],
        protocolo: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Preview — {protocolo}" if protocolo else "Preview das Imagens")
        self.setMinimumSize(520, 400)
        self.setModal(True)
        self.setStyleSheet(estilo_dialog())
        self._caminhos = caminhos
        self._build_ui(caminhos, protocolo)

    def _build_ui(self, caminhos: List[str], protocolo: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        lbl_titulo = QLabel(
            f"✅  {len(caminhos)} arte(s) gerada(s)"
            + (f"  —  {protocolo}" if protocolo else "")
        )
        lbl_titulo.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        lbl_titulo.setStyleSheet(f"color: {VERDE_PRIMARIO};")
        layout.addWidget(lbl_titulo)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: 1px solid {VERDE_BORDA}; border-radius: 6px; "
            f"background: {FUNDO_PRINCIPAL}; }}"
            f"QScrollBar:horizontal {{ background: {FUNDO_PRINCIPAL}; height: 8px; }}"
            f"QScrollBar::handle:horizontal {{ background: {VERDE_BORDA}; border-radius: 4px; }}"
        )

        container = QWidget()
        container.setStyleSheet(f"background: {FUNDO_PRINCIPAL};")
        row_layout = QHBoxLayout(container)
        row_layout.setContentsMargins(8, 8, 8, 8)
        row_layout.setSpacing(10)
        row_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        for caminho in caminhos:
            row_layout.addWidget(self._criar_thumb(caminho))

        scroll.setWidget(container)
        layout.addWidget(scroll, stretch=1)

        layout.addWidget(self._build_botoes())

    def _criar_thumb(self, caminho: str) -> QWidget:
        """Cria um widget de thumbnail para uma imagem.

        Args:
            caminho: Caminho absoluto do arquivo de imagem.

        Returns:
            Widget com thumbnail e nome do arquivo.
        """
        frame = QWidget()
        frame.setFixedWidth(THUMB_SIZE + 12)
        frame.setStyleSheet(
            f"QWidget {{ background: {FUNDO_CARD}; border: 1px solid {VERDE_BORDA}; "
            "border-radius: 6px; }}"
        )
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(6, 6, 6, 6)
        fl.setSpacing(4)

        lbl_img = QLabel()
        lbl_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_img.setFixedSize(THUMB_SIZE, THUMB_SIZE)

        px = QPixmap(caminho)
        if not px.isNull():
            px = px.scaled(
                THUMB_SIZE, THUMB_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            lbl_img.setPixmap(px)
        else:
            lbl_img.setText("⚠ Sem preview")
            lbl_img.setStyleSheet(f"color: {TEXTO_MUTED}; font-size: 11px; border: none;")

        fl.addWidget(lbl_img)

        lbl_nome = QLabel(Path(caminho).name)
        lbl_nome.setStyleSheet(f"color: {TEXTO_MUTED}; font-size: 9px; border: none;")
        lbl_nome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_nome.setWordWrap(True)
        fl.addWidget(lbl_nome)

        return frame

    def _build_botoes(self) -> QWidget:
        """Constrói a barra de botões do diálogo.

        Returns:
            Widget com botões Abrir Pasta e Fechar.
        """
        bar = QWidget()
        bar.setStyleSheet("QWidget { border: none; background: transparent; }")
        hl = QHBoxLayout(bar)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(8)

        btn_abrir = QPushButton("📂  Abrir Pasta")
        btn_abrir.setStyleSheet(
            f"QPushButton {{ background: {FUNDO_CARD}; color: {TEXTO_MUTED}; "
            f"border: 1px solid {VERDE_BORDA_SUTIL}; border-radius: 4px; padding: 6px 14px; }}"
            f"QPushButton:hover {{ background: {VERDE_ESCURO}; color: {VERDE_MEDIO}; }}"
        )
        btn_abrir.clicked.connect(self._abrir_pasta)

        btn_fechar = QPushButton("Fechar")
        btn_fechar.setDefault(True)
        btn_fechar.setStyleSheet(
            f"QPushButton {{ background: {VERDE_ESCURO}; color: {VERDE_PRIMARIO}; "
            f"border: 1px solid {VERDE_BORDA}; border-radius: 4px; "
            "padding: 6px 18px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: #004400; }}"
        )
        btn_fechar.clicked.connect(self.accept)

        hl.addWidget(btn_abrir)
        hl.addStretch()
        hl.addWidget(btn_fechar)
        return bar

    def _abrir_pasta(self) -> None:
        """Abre o explorador de arquivos na pasta das imagens geradas."""
        if not self._caminhos:
            return
        pasta = Path(self._caminhos[0]).parent
        if sys.platform == "win32":
            os.startfile(str(pasta))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(pasta)])
        else:
            subprocess.Popen(["xdg-open", str(pasta)])
