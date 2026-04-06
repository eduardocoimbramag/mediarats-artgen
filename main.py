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
    QPalette.ColorRole.Window:          "#121212",
    QPalette.ColorRole.WindowText:      "#E0E0E0",
    QPalette.ColorRole.Base:            "#1A1A1A",
    QPalette.ColorRole.AlternateBase:   "#1E1E1E",
    QPalette.ColorRole.ToolTipBase:     "#263238",
    QPalette.ColorRole.ToolTipText:     "#E0E0E0",
    QPalette.ColorRole.Text:            "#E0E0E0",
    QPalette.ColorRole.Button:          "#1E2A38",
    QPalette.ColorRole.ButtonText:      "#E0E0E0",
    QPalette.ColorRole.BrightText:      "#FFFFFF",
    QPalette.ColorRole.Link:            "#42A5F5",
    QPalette.ColorRole.Highlight:       "#1565C0",
    QPalette.ColorRole.HighlightedText: "#FFFFFF",
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
            background-color: #263238;
            color: #E0E0E0;
            border: 1px solid #37474F;
            border-radius: 4px;
            padding: 4px 8px;
        }
        QScrollBar:vertical {
            background: #1A1A1A;
            width: 10px;
            border-radius: 5px;
        }
        QScrollBar::handle:vertical {
            background: #37474F;
            min-height: 20px;
            border-radius: 5px;
        }
        QScrollBar::handle:vertical:hover {
            background: #546E7A;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
        QScrollBar:horizontal {
            background: #1A1A1A;
            height: 10px;
            border-radius: 5px;
        }
        QScrollBar::handle:horizontal {
            background: #37474F;
            min-width: 20px;
            border-radius: 5px;
        }
        QMessageBox {
            background-color: #1A1A1A;
            color: #E0E0E0;
        }
        QMessageBox QPushButton {
            background-color: #1565C0;
            color: #FFFFFF;
            border: none;
            border-radius: 4px;
            padding: 6px 20px;
            min-width: 80px;
        }
        QMessageBox QPushButton:hover {
            background-color: #1976D2;
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
