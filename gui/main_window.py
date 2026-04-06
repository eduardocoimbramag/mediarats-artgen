"""
Janela principal do Media Rats - Artgen.
Orquestra todos os painéis e gerencia a thread de geração.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, List

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QLabel, QStatusBar, QMessageBox, QFrame
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, pyqtSlot, QSize, QObject
)
from PyQt6.QtGui import QIcon, QFont, QPixmap, QColor, QPalette

from gui.dashboard import DashboardPanel
from gui.fila_panel import FilaPanel
from gui.log_panel import LogPanel
from gui.controles_panel import ControlesPanel
from gui.configuracoes_dialog import ConfiguracoesDialog
from excel.reader import ExcelReader, Solicitacao
from excel.writer import ExcelWriter
from utils.config import Config, settings
from utils.logger import logger
from utils.helpers import obter_versao, verificar_internet, verificar_arquivo_aberto, criar_pasta_output


class WorkerSignals(QObject):
    """Sinais emitidos pela thread de geração."""
    log = pyqtSignal(str, str)
    progresso = pyqtSignal(int, int)
    status_linha = pyqtSignal(str, str)
    info_dashboard = pyqtSignal(str, str, str)
    concluido = pyqtSignal(list)
    erro = pyqtSignal(str)
    login_necessario = pyqtSignal()


class GeracaoWorker(QThread):
    """Thread de geração para não bloquear a GUI.

    Args:
        solicitacao: Solicitação a processar.
        handler_existente: Driver já aberto a reutilizar (ex: após login manual).
    """

    def __init__(self, solicitacao: Solicitacao, handler_existente=None) -> None:
        super().__init__()
        self.solicitacao = solicitacao
        self.handler_existente = handler_existente
        self.handler = None
        self.signals = WorkerSignals()
        self._cancelado = False
        self._pausado = False
        self._generator = None

    def cancelar(self) -> None:
        """Sinaliza cancelamento para o worker."""
        self._cancelado = True
        if self._generator:
            self._generator.cancelar()

    def pausar(self, pausado: bool = True) -> None:
        """Pausa ou retoma a geração.

        Args:
            pausado: True para pausar.
        """
        self._pausado = pausado
        if self._generator:
            self._generator.pausar(pausado)

    def run(self) -> None:
        """Executa o fluxo de geração numa thread separada."""
        from bot.selenium_handler import SeleniumHandler
        from bot.adapta_generator import AdaptaGenerator

        sol = self.solicitacao
        self.signals.log.emit(f"Iniciando geração de {sol.protocolo}", "info")
        self.signals.info_dashboard.emit(sol.cliente, sol.protocolo, sol.tema)
        self.signals.status_linha.emit(sol.protocolo, "Gerando")

        if self.handler_existente and self.handler_existente.ativo:
            handler = self.handler_existente
            self.signals.log.emit("Reutilizando navegador já aberto.", "info")
        else:
            handler = SeleniumHandler(
                headless=Config.MODO_HEADLESS,
                timeout=Config.TIMEOUT_GERADOR,
            )
            self.signals.log.emit("Abrindo navegador...", "info")
            if not handler.iniciar():
                self.signals.erro.emit("Não foi possível iniciar o navegador.")
                self.signals.status_linha.emit(sol.protocolo, "Erro")
                return

        self.handler = handler

        pasta_output = Config.caminho_output_abs()
        generator = AdaptaGenerator(
            handler=handler,
            url_adapta=Config.URL_ADAPTA,
            pasta_output=pasta_output,
            timeout=Config.TIMEOUT_GERADOR,
        )
        self._generator = generator

        def _on_progresso(atual: int, total: int) -> None:
            self.signals.progresso.emit(atual, total)

        def _on_status(msg: str) -> None:
            if msg == "login_necessario":
                self.signals.login_necessario.emit()

        generator.definir_callbacks(progresso=_on_progresso, status=_on_status)

        self.signals.log.emit(f"Acessando {Config.URL_ADAPTA}...", "info")
        if not generator.acessar_adapta(email=Config.ADAPTA_EMAIL, senha=Config.ADAPTA_SENHA):
            self.signals.log.emit(
                "Login necessário. Faça login no navegador e clique em 'Iniciar Geração' novamente.",
                "aviso"
            )
            self.signals.login_necessario.emit()
            self.signals.status_linha.emit(sol.protocolo, "Pendente")
            return

        imagens = generator.gerar_solicitacao(sol)

        self.signals.concluido.emit([str(p) for p in imagens])
        self.signals.status_linha.emit(
            sol.protocolo, "Gerado" if imagens else "Erro"
        )


class MainWindow(QMainWindow):
    """Janela principal do Media Rats - Artgen."""

    VERSAO = obter_versao()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"Media Rats — Artgen v{self.VERSAO}")
        self.setMinimumSize(1024, 768)
        self._worker: Optional[GeracaoWorker] = None
        self._handler = None
        self._solicitacao_atual: Optional[Solicitacao] = None
        self._solicitacoes: List[Solicitacao] = []

        self._restaurar_geometria()
        self._build_ui()
        self._conectar_logger()
        self._carregar_planilha()

    def _restaurar_geometria(self) -> None:
        """Restaura tamanho e posição da janela das preferências salvas."""
        w = settings.get("janela_largura", 1280)
        h = settings.get("janela_altura", 800)
        x = settings.get("janela_x", 100)
        y = settings.get("janela_y", 100)
        self.resize(w, h)
        self.move(x, y)

    def _build_ui(self) -> None:
        """Constrói toda a interface da janela principal."""
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(12, 8, 12, 8)
        root_layout.setSpacing(8)

        root_layout.addWidget(self._build_header())

        self._dashboard = DashboardPanel()
        root_layout.addWidget(self._dashboard)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #30363D;")
        root_layout.addWidget(sep)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(6)
        splitter.setStyleSheet(
            "QSplitter::handle { background: #2D3F50; border-radius: 3px; }"
            "QSplitter::handle:hover { background: #1565C0; }"
        )

        self._fila_panel = FilaPanel()
        self._log_panel = LogPanel()
        splitter.addWidget(self._fila_panel)
        splitter.addWidget(self._log_panel)

        pos = settings.get("splitter_posicao", [600, 400])
        splitter.setSizes(pos)
        root_layout.addWidget(splitter, stretch=1)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #30363D;")
        root_layout.addWidget(sep2)

        self._controles = ControlesPanel()
        root_layout.addWidget(self._controles)

        self._controles.sinal_iniciar.connect(self._iniciar_geracao)
        self._controles.sinal_pausar.connect(self._pausar_geracao)
        self._controles.sinal_cancelar.connect(self._cancelar_geracao)
        self._controles.sinal_recarregar.connect(self._carregar_planilha)
        self._controles.sinal_abrir_output.connect(self._abrir_output)
        self._controles.sinal_configuracoes.connect(self._abrir_configuracoes)
        self._controles.sinal_clientes.connect(self._abrir_clientes)

        self._fila_panel.solicitacao_selecionada.connect(self._on_solicitacao_selecionada)

        self._status_bar = QStatusBar()
        self._status_bar.setStyleSheet(
            "QStatusBar { background: #161B22; color: #8B949E; font-size: 11px; border-top: 1px solid #30363D; }"
        )
        self.setStatusBar(self._status_bar)
        self._lbl_status = QLabel("Pronto")
        self._lbl_status.setStyleSheet("color: #4CAF50; font-weight: bold;")
        self._lbl_versao = QLabel(f"v{self.VERSAO}")
        self._lbl_versao.setStyleSheet("color: #546E7A;")
        self._status_bar.addPermanentWidget(self._lbl_versao)
        self._status_bar.addWidget(self._lbl_status)

    def _build_header(self) -> QWidget:
        """Constrói o cabeçalho com logo e título.

        Returns:
            Widget do cabeçalho.
        """
        header = QWidget()
        header.setFixedHeight(56)
        header.setStyleSheet(
            "QWidget { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, "
            "stop:0 #0D1B2A, stop:1 #1A237E); "
            "border-radius: 8px; }"
        )
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 0, 16, 0)

        logo_path = Path(__file__).parent.parent / "assets" / "logo.png"
        lbl_logo = QLabel()
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path)).scaled(
                40, 40, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            lbl_logo.setPixmap(pixmap)
        else:
            lbl_logo.setText("🐀")
            lbl_logo.setStyleSheet("font-size: 28px;")
        layout.addWidget(lbl_logo)

        lbl_titulo = QLabel("Media Rats — Artgen")
        lbl_titulo.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        lbl_titulo.setStyleSheet("color: #FFFFFF; letter-spacing: 1px;")
        layout.addWidget(lbl_titulo)

        lbl_sub = QLabel("Gerador Automático de Artes para Redes Sociais")
        lbl_sub.setStyleSheet("color: #90CAF9; font-size: 11px;")
        layout.addStretch()
        layout.addWidget(lbl_sub)

        return header

    def _conectar_logger(self) -> None:
        """Conecta o sistema de log ao painel de log da GUI."""
        logger.definir_callback(
            lambda msg, tipo: self._log_panel.adicionar_mensagem(msg, tipo)
        )

    def _carregar_planilha(self) -> None:
        """Lê a planilha e atualiza a fila de solicitações."""
        caminho = Config.caminho_planilha_abs()
        logger.info(f"Carregando planilha: {caminho}")

        if verificar_arquivo_aberto(caminho):
            QMessageBox.warning(
                self,
                "Planilha em uso",
                "O arquivo Excel parece estar aberto em outro programa.\n"
                "Feche-o antes de continuar.",
            )
            return

        try:
            reader = ExcelReader(caminho)
            erros = reader.verificar_planilha()
            if erros:
                QMessageBox.critical(self, "Erro na Planilha", "\n".join(erros))
                return

            writer = ExcelWriter(caminho)
            writer.criar_estrutura_planilha()

            self._solicitacoes = reader.ler_solicitacoes(apenas_pendentes=False)
            self._fila_panel.carregar_solicitacoes(self._solicitacoes)

            pendentes = [s for s in self._solicitacoes if s.status.lower() in {"planejado", "pendente"}]
            logger.sucesso(
                f"Planilha carregada: {len(self._solicitacoes)} solicitação(ões) "
                f"({len(pendentes)} pendente(s))."
            )
            self._atualizar_status("Planilha carregada com sucesso.")

        except FileNotFoundError as exc:
            logger.erro(f"Planilha não encontrada: {exc}")
            QMessageBox.critical(
                self, "Arquivo não encontrado",
                f"Planilha não localizada em:\n{caminho}\n\n"
                "Verifique o caminho nas Configurações."
            )
        except Exception as exc:
            logger.erro(f"Erro ao carregar planilha: {exc}")
            QMessageBox.critical(self, "Erro", str(exc))

    @pyqtSlot(object)
    def _on_solicitacao_selecionada(self, sol: Solicitacao) -> None:
        """Atualiza UI ao selecionar uma solicitação na fila.

        Args:
            sol: Solicitação selecionada.
        """
        self._solicitacao_atual = sol
        self._dashboard.atualizar_info(sol.cliente, sol.protocolo, sol.tema)
        self._dashboard.atualizar_progresso(0, len(sol.prompts_validos()))
        self._atualizar_status(f"Selecionado: {sol.protocolo} — {sol.tema}")

    @pyqtSlot()
    def _iniciar_geracao(self) -> None:
        """Valida e inicia a geração da solicitação selecionada."""
        sol = self._fila_panel.solicitacao_atual()
        if sol is None:
            QMessageBox.warning(self, "Sem seleção", "Selecione uma solicitação na fila.")
            return

        if not verificar_internet():
            QMessageBox.critical(
                self, "Sem Internet",
                "Não foi possível detectar conexão com a internet.\n"
                "Verifique sua rede antes de continuar."
            )
            return

        pasta = Config.caminho_output_abs() / sol.protocolo.replace("#", "_")
        if pasta.exists() and any(pasta.iterdir()):
            resp = QMessageBox.question(
                self,
                "Pasta existente",
                f"A pasta de output para {sol.protocolo} já possui arquivos.\n"
                "Deseja limpar e gerar novamente?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if resp == QMessageBox.StandardButton.No:
                return
            for f in pasta.iterdir():
                if f.is_file():
                    f.unlink()

        self._solicitacao_atual = sol
        self._worker = GeracaoWorker(sol, handler_existente=self._handler)

        self._worker.signals.log.connect(self._log_panel.adicionar_mensagem)
        self._worker.signals.progresso.connect(self._dashboard.atualizar_progresso)
        self._worker.signals.status_linha.connect(self._fila_panel.atualizar_status_linha)
        self._worker.signals.info_dashboard.connect(self._dashboard.atualizar_info)
        self._worker.signals.concluido.connect(self._on_geracao_concluida)
        self._worker.signals.erro.connect(self._on_geracao_erro)
        self._worker.signals.login_necessario.connect(self._on_login_necessario)
        self._worker.finished.connect(self._on_worker_finalizado)

        self._controles.set_estado_gerando()
        self._atualizar_status("Gerando...", "gerando")
        self._worker.start()

    @pyqtSlot()
    def _pausar_geracao(self) -> None:
        """Pausa ou retoma a geração."""
        if self._worker and self._worker.isRunning():
            pausado = not getattr(self._worker, "_pausado", False)
            self._worker.pausar(pausado)
            if pausado:
                self._atualizar_status("Pausado", "pausado")
                logger.aviso("Geração pausada pelo usuário.")
            else:
                self._atualizar_status("Gerando...", "gerando")
                logger.info("Geração retomada.")

    @pyqtSlot()
    def _cancelar_geracao(self) -> None:
        """Cancela a geração em andamento."""
        if self._worker and self._worker.isRunning():
            resp = QMessageBox.question(
                self,
                "Cancelar Geração",
                "Deseja realmente cancelar a geração?\nO navegador será fechado.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if resp == QMessageBox.StandardButton.Yes:
                self._worker.cancelar()
                logger.aviso("Cancelamento solicitado...")
                if self._handler:
                    self._handler.fechar()
                    self._handler = None
                if self._solicitacao_atual:
                    self._fila_panel.atualizar_status_linha(
                        self._solicitacao_atual.protocolo, "Cancelado"
                    )

    @pyqtSlot()
    def _on_worker_finalizado_com_login(self) -> None:
        """Chamado quando worker termina por causa de login — não fecha o handler."""
        pass

    @pyqtSlot(list)
    def _on_geracao_concluida(self, caminhos: list) -> None:
        """Atualiza planilha e interface após conclusão da geração.

        Args:
            caminhos: Lista de caminhos das imagens geradas.
        """
        sol = self._solicitacao_atual
        if not sol:
            return

        caminho_planilha = Config.caminho_planilha_abs()
        try:
            writer = ExcelWriter(caminho_planilha)
            writer.atualizar_status(sol, "Gerado")
            caminhos_rel = [
                str(Path(c).relative_to(Config.caminho_output_abs()))
                for c in caminhos
            ]
            writer.registrar_avaliacao(sol, caminhos_rel)
            logger.sucesso(f"Planilha atualizada para {sol.protocolo}.")
        except Exception as exc:
            logger.erro(f"Erro ao atualizar planilha: {exc}")

        if Config.FECHAR_NAVEGADOR_APOS_CONCLUSAO:
            if self._handler:
                self._handler.fechar()
                self._handler = None

        QMessageBox.information(
            self,
            "Geração Concluída",
            f"✅ {sol.protocolo} — {len(caminhos)} arte(s) gerada(s) com sucesso!\n"
            f"Salvas em: output/{sol.protocolo.replace('#', '_')}/",
        )

    @pyqtSlot(str)
    def _on_geracao_erro(self, mensagem: str) -> None:
        """Trata erros críticos da geração.

        Args:
            mensagem: Descrição do erro.
        """
        logger.erro(f"Erro crítico: {mensagem}")
        QMessageBox.critical(self, "Erro na Geração", mensagem)
        self._atualizar_status("Erro", "erro")

    @pyqtSlot()
    def _on_login_necessario(self) -> None:
        """Mantém o navegador aberto e orienta o usuário sobre o login manual."""
        if self._worker:
            self._handler = self._worker.handler
        QMessageBox.information(
            self,
            "Login Necessário",
            f"O navegador está aberto em {Config.URL_ADAPTA}.\n\n"
            "➡  Faça o login manualmente no navegador.\n"
            "➡  Depois clique em 'Iniciar Geração' novamente.\n\n"
            "💡 Dica: configure e-mail e senha em Configurações → Login\n"
            "     para login automático nas próximas vezes.",
        )

    @pyqtSlot()
    def _on_worker_finalizado(self) -> None:
        """Restaura estado dos controles quando a thread termina."""
        self._controles.set_estado_inicial()
        if self._lbl_status.text() not in ("Erro", "Cancelado"):
            self._atualizar_status("Pronto")
        self._dashboard.atualizar_progresso(0, 0)

    @pyqtSlot()
    def _abrir_output(self) -> None:
        """Abre o explorador de arquivos na pasta de output."""
        pasta = Config.caminho_output_abs()
        pasta.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(pasta))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(pasta)])
        else:
            subprocess.Popen(["xdg-open", str(pasta)])

    @pyqtSlot()
    def _abrir_configuracoes(self) -> None:
        """Abre o diálogo de configurações."""
        dlg = ConfiguracoesDialog(self)
        if dlg.exec():
            Config.recarregar()
            logger.info("Configurações salvas e recarregadas.")
            self._carregar_planilha()

    @pyqtSlot()
    def _abrir_clientes(self) -> None:
        """Abre o diálogo de gerenciamento de clientes."""
        from gui.clientes_dialog import ClientesDialog
        dlg = ClientesDialog(Config.caminho_planilha_abs(), self)
        dlg.exec()
        self._carregar_planilha()

    def _atualizar_status(self, texto: str, tipo: str = "ok") -> None:
        """Atualiza a barra de status.

        Args:
            texto: Texto a exibir.
            tipo: 'ok', 'gerando', 'pausado', 'erro'.
        """
        cores = {
            "ok":      "#4CAF50",
            "gerando": "#2196F3",
            "pausado": "#FF9800",
            "erro":    "#F44336",
        }
        cor = cores.get(tipo, "#4CAF50")
        self._lbl_status.setText(texto)
        self._lbl_status.setStyleSheet(f"color: {cor}; font-weight: bold;")

    def closeEvent(self, event) -> None:
        """Salva preferências e confirma fechamento se houver geração ativa.

        Args:
            event: Evento de fechamento.
        """
        if self._worker and self._worker.isRunning():
            resp = QMessageBox.question(
                self,
                "Sair",
                "Uma geração está em andamento. Deseja cancelar e sair?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if resp == QMessageBox.StandardButton.No:
                event.ignore()
                return
            self._worker.cancelar()
            self._worker.wait(3000)

        if self._handler:
            self._handler.fechar()
            self._handler = None

        settings.set("janela_largura", self.width())
        settings.set("janela_altura", self.height())
        settings.set("janela_x", self.x())
        settings.set("janela_y", self.y())
        settings.salvar()
        event.accept()
