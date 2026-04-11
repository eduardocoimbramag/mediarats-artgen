"""
Media Rats - Artgen
Ponto de entrada principal do programa.
Versão: 1.0.0
"""

import sys
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPalette, QColor

from utils.helpers import obter_versao


VERSAO = obter_versao()

DARK_PALETTE_COLORS = {
    QPalette.ColorRole.Window:          "#000000",
    QPalette.ColorRole.WindowText:      "#D0D0D0",
    QPalette.ColorRole.Base:            "#0d0d0d",
    QPalette.ColorRole.AlternateBase:   "#111111",
    QPalette.ColorRole.ToolTipBase:     "#111111",
    QPalette.ColorRole.ToolTipText:     "#00ff00",
    QPalette.ColorRole.Text:            "#D0D0D0",
    QPalette.ColorRole.Button:          "#111111",
    QPalette.ColorRole.ButtonText:      "#D0D0D0",
    QPalette.ColorRole.BrightText:      "#FFFFFF",
    QPalette.ColorRole.Link:            "#00cc00",
    QPalette.ColorRole.Highlight:       "#003300",
    QPalette.ColorRole.HighlightedText: "#00ff00",
}


def aplicar_tema_escuro(app: QApplication) -> None:
    """Aplica paleta de cores escura à aplicação.

    Args:
        app: Instância da QApplication.
    """
    app.setStyle("Fusion")
    palette = QPalette()
    for role, hex_color in DARK_PALETTE_COLORS.items():
        palette.setColor(role, QColor(hex_color))
    app.setPalette(palette)

    app.setStyleSheet(
        """
        QToolTip {
            background-color: #111111;
            color: #00ff00;
            border: 1px solid #1a3a1a;
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 11px;
        }
        QScrollBar:vertical {
            background: #0d0d0d;
            width: 8px;
            border-radius: 4px;
        }
        QScrollBar::handle:vertical {
            background: #2a2a2a;
            min-height: 20px;
            border-radius: 4px;
        }
        QScrollBar::handle:vertical:hover {
            background: #004400;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
        QScrollBar:horizontal {
            background: #0d0d0d;
            height: 8px;
            border-radius: 4px;
        }
        QScrollBar::handle:horizontal {
            background: #2a2a2a;
            min-width: 20px;
            border-radius: 4px;
        }
        QScrollBar::handle:horizontal:hover {
            background: #004400;
        }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            width: 0px;
        }
        QMessageBox {
            background-color: #0d0d0d;
            color: #D0D0D0;
        }
        QMessageBox QPushButton {
            background-color: #004400;
            color: #00ff00;
            border: none;
            border-radius: 4px;
            padding: 6px 20px;
            min-width: 80px;
            font-weight: bold;
        }
        QMessageBox QPushButton:hover {
            background-color: #005500;
        }
        """
    )


def main() -> None:
    """Função principal: inicializa a aplicação Qt e exibe a janela principal."""
    os.makedirs(BASE_DIR / "output", exist_ok=True)
    os.makedirs(BASE_DIR / "logs", exist_ok=True)

    app = QApplication(sys.argv)
    app.setApplicationName("Media Rats - Artgen")
    app.setApplicationVersion(VERSAO)
    app.setOrganizationName("Media Rats")

    logo_path = BASE_DIR / "logomr.png"
    if not logo_path.exists():
        logo_path = BASE_DIR / "assets" / "logo.png"
    if logo_path.exists():
        app.setWindowIcon(QIcon(str(logo_path)))

    aplicar_tema_escuro(app)

    try:
        from gui.main_window import MainWindow
        janela = MainWindow()
        janela.show()
    except Exception as exc:
        QMessageBox.critical(
            None,
            "Erro ao inicializar",
            f"Erro crítico ao iniciar o Media Rats Artgen:\n\n{exc}\n\n"
            "Verifique o arquivo de log em: logs/artgen.log",
        )
        raise

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
