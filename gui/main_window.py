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
    Qt, pyqtSlot, QSize
)
from PyQt6.QtGui import QIcon, QFont, QPixmap, QColor, QPalette

from gui.dashboard import DashboardPanel
from gui.fila_panel import FilaPanel
from gui.log_panel import LogPanel
from gui.controles_panel import ControlesPanel
from gui.configuracoes_dialog import ConfiguracoesDialog
from excel.reader import ExcelReader, Solicitacao, Cliente
from excel.writer import ExcelWriter
from utils.config import Config, settings
from utils.logger import logger
from utils.helpers import obter_versao, verificar_internet, verificar_arquivo_aberto, criar_pasta_output
from bot.geracao_worker import GeracaoWorker, FilaAutoWorker, WorkerSignals


class MainWindow(QMainWindow):
    """Janela principal do Media Rats - Artgen."""

    VERSAO = obter_versao()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"Media Rats — Artgen v{self.VERSAO}")
        self.setMinimumSize(1024, 768)
        self._worker: Optional[GeracaoWorker] = None
        self._fila_worker: Optional[FilaAutoWorker] = None
        self._handler = None
        self._solicitacao_atual: Optional[Solicitacao] = None
        self._solicitacoes: List[Solicitacao] = []
        self._clientes: List[Cliente] = []

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
        sep.setStyleSheet("color: #1a2a1a;")
        root_layout.addWidget(sep)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(6)
        splitter.setStyleSheet(
            "QSplitter::handle { background: #1a2a1a; border-radius: 3px; }"
            "QSplitter::handle:hover { background: #004400; }"
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
        sep2.setStyleSheet("color: #1a2a1a;")
        root_layout.addWidget(sep2)

        self._controles = ControlesPanel()
        root_layout.addWidget(self._controles)

        self._controles.sinal_iniciar.connect(self._iniciar_geracao)
        self._controles.sinal_processar_fila.connect(self._processar_fila_completa)
        self._controles.sinal_pausar.connect(self._pausar_geracao)
        self._controles.sinal_cancelar.connect(self._cancelar_geracao)
        self._controles.sinal_recarregar.connect(self._carregar_planilha)
        self._controles.sinal_abrir_output.connect(self._abrir_output)
        self._controles.sinal_configuracoes.connect(self._abrir_configuracoes)
        self._controles.sinal_clientes.connect(self._abrir_clientes)
        self._controles.sinal_criar_protocolo.connect(self._criar_protocolo)
        self._controles.sinal_remover_protocolo.connect(self._remover_protocolo)

        self._fila_panel.solicitacao_selecionada.connect(self._on_solicitacao_selecionada)

        self._status_bar = QStatusBar()
        self._status_bar.setStyleSheet(
            "QStatusBar { background: #000000; color: #444444; font-size: 11px; border-top: 1px solid #1a2a1a; }"
        )
        self.setStatusBar(self._status_bar)
        self._lbl_status = QLabel("Pronto")
        self._lbl_status.setStyleSheet("color: #00cc00; font-weight: bold;")
        self._lbl_versao = QLabel(f"v{self.VERSAO}")
        self._lbl_versao.setStyleSheet("color: #336633;")
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
            "stop:0 #000000, stop:0.6 #020d02, stop:1 #001a00); "
            "border-radius: 8px; border: 1px solid #1a3a1a; }"
        )
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        logo_path = Path(__file__).parent.parent / "logomr.png"
        if not logo_path.exists():
            logo_path = Path(__file__).parent.parent / "assets" / "logo.png"
        lbl_logo = QLabel()
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path)).scaled(
                40, 40, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            lbl_logo.setPixmap(pixmap)
        else:
            lbl_logo.setText("MR")
            lbl_logo.setStyleSheet(
                "color: #00ff00; font-size: 20px; font-weight: bold; "
                "border: 2px solid #00ff00; border-radius: 4px; padding: 2px 6px;"
            )
        layout.addWidget(lbl_logo)

        lbl_titulo = QLabel("Media Rats — Artgen")
        lbl_titulo.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        lbl_titulo.setStyleSheet("color: #00ff00; letter-spacing: 1px;")
        layout.addWidget(lbl_titulo)

        lbl_sub = QLabel("Gerador Automático de Artes para Redes Sociais")
        lbl_sub.setStyleSheet("color: #336633; font-size: 11px;")
        layout.addStretch()
        layout.addWidget(lbl_sub)

        return header

    def _conectar_logger(self) -> None:
        """Conecta o sinal do logger ao painel de log da GUI."""
        logger.mensagem_emitida.connect(self._log_panel.adicionar_mensagem)

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

            self._clientes = reader.ler_clientes()
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
        self._worker = GeracaoWorker(
            sol, handler_existente=self._handler, clientes=self._clientes
        )

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
    def _processar_fila_completa(self) -> None:
        """Inicia processamento automático de todas as solicitações pendentes."""
        pendentes = [
            s for s in self._solicitacoes
            if s.status.lower() in FilaAutoWorker.STATUS_PENDENTES
        ]
        if not pendentes:
            QMessageBox.information(
                self,
                "Fila Vazia",
                "Não há solicitações com status 'Planejado' ou 'Pendente' na fila.",
            )
            return

        if not verificar_internet():
            QMessageBox.critical(
                self, "Sem Internet",
                "Não foi possível detectar conexão com a internet."
            )
            return

        resp = QMessageBox.question(
            self,
            "Processar Fila Completa",
            f"Serão processadas {len(pendentes)} solicitação(oes) pendente(s) em sequência.\n"
            "O navegador será mantido aberto entre as gerações.\n\n"
            "Deseja continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return

        self._fila_worker = FilaAutoWorker(pendentes, clientes=self._clientes)

        self._fila_worker.sinal_avancar.connect(self._dashboard.atualizar_progresso)
        self._fila_worker.sinal_item_iniciado.connect(self._on_fila_item_iniciado)
        self._fila_worker.sinal_item_concluido.connect(self._on_fila_item_concluido)
        self._fila_worker.sinal_item_erro.connect(self._on_fila_item_erro)
        self._fila_worker.sinal_login_necessario.connect(self._on_login_necessario)
        self._fila_worker.sinal_fila_concluida.connect(self._on_fila_concluida)
        self._fila_worker.finished.connect(self._on_worker_finalizado)

        self._controles.set_estado_gerando()
        self._atualizar_status(f"Processando fila: 0/{len(pendentes)}...", "gerando")
        self._fila_worker.start()

    @pyqtSlot(str)
    def _on_fila_item_iniciado(self, protocolo: str) -> None:
        """Atualiza UI quando o processamento de um item da fila começa.

        Args:
            protocolo: Protocolo da solicitação sendo gerada.
        """
        self._fila_panel.atualizar_status_linha(protocolo, "Gerando")
        logger.info(f"[Fila] Iniciando: {protocolo}")
        self._atualizar_status(f"Gerando: {protocolo}", "gerando")

    @pyqtSlot(str, list)
    def _on_fila_item_concluido(self, protocolo: str, caminhos: list) -> None:
        """Registra conclusão de um item da fila na planilha e atualiza a UI.

        Args:
            protocolo: Protocolo concluído.
            caminhos: Caminhos das imagens geradas.
        """
        self._fila_panel.atualizar_status_linha(protocolo, "Gerado")
        sol = next((s for s in self._solicitacoes if s.protocolo == protocolo), None)
        if sol:
            try:
                caminhos_rel = [
                    str(Path(c).relative_to(Config.caminho_output_abs()))
                    for c in caminhos
                ]
                writer = ExcelWriter(Config.caminho_planilha_abs())
                writer.registrar_conclusao(sol, caminhos_rel)
                logger.sucesso(f"[Fila] {protocolo} concluído — {len(caminhos)} arte(s).")
            except Exception as exc:
                logger.erro(f"[Fila] Erro ao salvar {protocolo}: {exc}")

    @pyqtSlot(str, str)
    def _on_fila_item_erro(self, protocolo: str, mensagem: str) -> None:
        """Registra falha de um item da fila.

        Args:
            protocolo: Protocolo que falhou.
            mensagem: Descrição do erro.
        """
        self._fila_panel.atualizar_status_linha(protocolo, "Erro")
        logger.erro(f"[Fila] {protocolo} falhou: {mensagem}")

    @pyqtSlot(int, int)
    def _on_fila_concluida(self, concluidos: int, erros: int) -> None:
        """Exibe resumo ao final do processamento da fila completa.

        Args:
            concluidos: Número de solicitações geradas com sucesso.
            erros: Número de solicitações que falharam.
        """
        if self._fila_worker:
            self._handler = self._fila_worker._handler
        partes = [f"✅ {concluidos} gerada(s) com sucesso"]
        if erros:
            partes.append(f"❌ {erros} com erro")
        QMessageBox.information(
            self,
            "Fila Concluída",
            "Processamento da fila finalizado!\n\n" + "\n".join(partes),
        )
        logger.sucesso(f"[Fila] Processamento concluído: {concluidos} ok, {erros} erro(s).")

    @pyqtSlot()
    def _pausar_geracao(self) -> None:
        """Pausa ou retoma a geração (individual ou fila)."""
        worker_ativo = (
            self._fila_worker if (self._fila_worker and self._fila_worker.isRunning())
            else self._worker
        )
        if worker_ativo and worker_ativo.isRunning():
            pausado = not getattr(worker_ativo, "_pausado", False)
            worker_ativo.pausar(pausado)
            if pausado:
                self._atualizar_status("Pausado", "pausado")
                logger.aviso("Geração pausada pelo usuário.")
            else:
                self._atualizar_status("Gerando...", "gerando")
                logger.info("Geração retomada.")

    @pyqtSlot()
    def _cancelar_geracao(self) -> None:
        """Cancela a geração em andamento (individual ou fila)."""
        fila_ativa = self._fila_worker and self._fila_worker.isRunning()
        worker_ativo = self._worker and self._worker.isRunning()
        if not fila_ativa and not worker_ativo:
            return

        resp = QMessageBox.question(
            self,
            "Cancelar Geração",
            "Deseja realmente cancelar a geração?\nO navegador será fechado.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if resp == QMessageBox.StandardButton.Yes:
            if fila_ativa:
                self._fila_worker.cancelar()
                logger.aviso("Cancelamento da fila solicitado...")
            if worker_ativo:
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
            caminhos_rel = [
                str(Path(c).relative_to(Config.caminho_output_abs()))
                for c in caminhos
            ]
            writer = ExcelWriter(caminho_planilha)
            writer.registrar_conclusao(sol, caminhos_rel)
            logger.sucesso(f"Planilha atualizada para {sol.protocolo}.")
        except Exception as exc:
            logger.erro(f"Erro ao atualizar planilha: {exc}")

        fechar = Config.FECHAR_NAVEGADOR_APOS_CONCLUSAO
        origem = os.getenv("FECHAR_NAVEGADOR_APOS_CONCLUSAO", "<não definido no .env>")
        logger.info(
            f"[Browser] FECHAR_NAVEGADOR_APOS_CONCLUSAO={fechar} "
            f"(valor no .env: '{origem}')"
        )
        if fechar:
            logger.info("[Browser] Fechando navegador conforme configuração.")
            if self._handler:
                self._handler.fechar()
                self._handler = None
        else:
            logger.info("[Browser] Navegador mantido aberto conforme configuração.")

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

    @pyqtSlot()
    def _criar_protocolo(self) -> None:
        """Abre o diálogo de criação de protocolo e recarrega a fila ao confirmar."""
        from gui.criar_protocolo_dialog import CriarProtocoloDialog
        dlg = CriarProtocoloDialog(Config.caminho_planilha_abs(), self)
        if dlg.exec() == dlg.DialogCode.Accepted and dlg.solicitacao is not None:
            sol = dlg.solicitacao
            logger.sucesso(
                f"Protocolo '{sol.protocolo}' criado — {sol.cliente} / {sol.tema}"
            )
            self._carregar_planilha()
            self._atualizar_status(f"Protocolo {sol.protocolo} adicionado à fila.")

    @pyqtSlot()
    def _remover_protocolo(self) -> None:
        """Remove permanentemente o protocolo selecionado da fila e da planilha.

        Apaga a linha inteira da aba CONTEUDOS (remoção definitiva, não apenas
        troca de status) e remove da tabela visual.
        Trata com segurança: fila vazia, nenhum item selecionado e falha de escrita.
        """
        sol = self._fila_panel.solicitacao_atual()

        if sol is None:
            QMessageBox.information(
                self,
                "Nenhum item selecionado",
                "Selecione um protocolo na fila antes de removê-lo.",
            )
            return

        if self._worker and self._worker.isRunning():
            if sol.protocolo == (self._worker.solicitacao.protocolo if self._worker.solicitacao else ""):
                QMessageBox.warning(
                    self,
                    "Protocolo em geração",
                    f"O protocolo '{sol.protocolo}' está sendo gerado no momento.\n"
                    "Cancele a geração antes de removê-lo da fila.",
                )
                return

        resp = QMessageBox.question(
            self,
            "Confirmar Remoção",
            f"Deseja remover permanentemente o protocolo?\n\n"
            f"  Protocolo: {sol.protocolo}\n"
            f"  Cliente:   {sol.cliente}\n"
            f"  Tema:      {sol.tema}\n\n"
            "O item será apagado da planilha e não poderá ser recuperado.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return

        try:
            writer = ExcelWriter(Config.caminho_planilha_abs())
            removido_excel = writer.remover_solicitacao(sol)
            if not removido_excel:
                logger.aviso(
                    f"Protocolo '{sol.protocolo}' não encontrado na planilha "
                    "(pode já ter sido removido)."
                )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Erro ao Remover",
                f"Não foi possível remover da planilha:\n{exc}\n\n"
                "O item foi removido da fila visível mas pode reaparecer ao recarregar.",
            )
            logger.aviso(f"Falha ao remover '{sol.protocolo}' da planilha: {exc}")

        removido = self._fila_panel.remover_solicitacao(sol.protocolo)
        if removido:
            logger.info(f"Protocolo '{sol.protocolo}' removido permanentemente.")
            self._atualizar_status(f"Protocolo {sol.protocolo} removido.")
        else:
            logger.aviso(f"Protocolo '{sol.protocolo}' não encontrado na tabela visual.")

    def _atualizar_status(self, texto: str, tipo: str = "ok") -> None:
        """Atualiza a barra de status.

        Args:
            texto: Texto a exibir.
            tipo: 'ok', 'gerando', 'pausado', 'erro'.
        """
        cores = {
            "ok":      "#00cc00",
            "gerando": "#00ff00",
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
        ativo = (
            (self._fila_worker and self._fila_worker.isRunning())
            or (self._worker and self._worker.isRunning())
        )
        if ativo:
            resp = QMessageBox.question(
                self,
                "Sair",
                "Uma geração está em andamento. Deseja cancelar e sair?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if resp == QMessageBox.StandardButton.No:
                event.ignore()
                return
            if self._fila_worker and self._fila_worker.isRunning():
                self._fila_worker.cancelar()
                self._fila_worker.wait(3000)
            if self._worker and self._worker.isRunning():
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
