"""
Workers de geração desacoplados da camada de UI.

Define WorkerSignals, GeracaoWorker e FilaAutoWorker como QThread independentes
que podem ser testados sem depender de MainWindow.
"""

from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from excel.reader import ExcelReader, Solicitacao, Cliente
from utils.config import Config
from utils.logger import logger


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
        clientes: Lista de clientes já carregada para evitar re-leitura da planilha.
    """

    def __init__(
        self,
        solicitacao: Solicitacao,
        handler_existente=None,
        clientes: Optional[List[Cliente]] = None,
    ) -> None:
        super().__init__()
        self.solicitacao = solicitacao
        self.handler_existente = handler_existente
        self._clientes_cache = clientes
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

        cliente_obj = self._carregar_perfil_cliente(sol.codigo_cliente)

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
            if msg in ("login_necessario", "login_falhou"):
                self.signals.login_necessario.emit()

        generator.definir_callbacks(progresso=_on_progresso, status=_on_status)

        tem_credenciais = bool(
            Config.ADAPTA_EMAIL and Config.ADAPTA_EMAIL.strip()
            and Config.ADAPTA_SENHA and Config.ADAPTA_SENHA.strip()
        )

        self.signals.log.emit(f"Acessando {Config.URL_ADAPTA}...", "info")
        if not generator.acessar_adapta(email=Config.ADAPTA_EMAIL, senha=Config.ADAPTA_SENHA):
            if tem_credenciais:
                self.signals.log.emit(
                    "Login automático falhou. Possíveis causas: campos da página não "
                    "carregaram (tente aguardar e repetir) ou credenciais inválidas "
                    "(verifique em Configurações → Login). "
                    "Veja o log para o motivo exato.",
                    "aviso",
                )
            else:
                self.signals.log.emit(
                    "Credenciais não configuradas. Faça login no navegador aberto "
                    "e clique em 'Iniciar Geração' novamente.",
                    "aviso",
                )
            self.signals.login_necessario.emit()
            self.signals.status_linha.emit(sol.protocolo, "Pendente")
            return

        imagens = generator.gerar_solicitacao(sol, cliente=cliente_obj)

        self.signals.concluido.emit([str(p) for p in imagens])
        self.signals.status_linha.emit(
            sol.protocolo, "Gerado" if imagens else "Erro"
        )

    def _carregar_perfil_cliente(self, codigo_cliente: str):
        """Carrega o perfil completo do cliente a partir da planilha.

        Usa a lista de clientes em cache (passada no construtor) quando disponível,
        evitando reabrir o arquivo Excel a cada geração.

        Args:
            codigo_cliente: Código do cliente (ex: DUDE).

        Returns:
            Instância de ``excel.reader.Cliente`` ou None.
        """
        try:
            clientes = self._clientes_cache
            if clientes is None:
                reader = ExcelReader(Config.caminho_planilha_abs())
                clientes = reader.ler_clientes()
            codigo_upper = codigo_cliente.strip().upper()
            for c in clientes:
                if c.codigo.strip().upper() == codigo_upper:
                    self.signals.log.emit(
                        f"[Composer] Perfil do cliente '{c.nome}' carregado.",
                        "info",
                    )
                    return c
            self.signals.log.emit(
                f"[Composer] Cliente '{codigo_cliente}' não encontrado na aba CLIENTES.",
                "aviso",
            )
        except Exception as exc:
            self.signals.log.emit(
                f"[Composer] Falha ao carregar perfil do cliente: {exc}",
                "aviso",
            )
        return None


class FilaAutoWorker(QThread):
    """Thread que percorre todas as solicitações pendentes em série.

    Para cada solicitação com status 'Planejado' ou 'Pendente', cria e
    executa um ``GeracaoWorker`` sequencialmente. O navegador é mantido
    aberto entre solicitações para acelerar o processo.

    Args:
        solicitacoes: Lista de solicitações a processar em ordem.
        clientes: Lista de clientes já carregada para evitar re-leitura da planilha.
    """

    sinal_avancar = pyqtSignal(int, int)
    sinal_item_iniciado = pyqtSignal(str)
    sinal_item_concluido = pyqtSignal(str, list)
    sinal_item_erro = pyqtSignal(str, str)
    sinal_login_necessario = pyqtSignal()
    sinal_fila_concluida = pyqtSignal(int, int)

    STATUS_PENDENTES = {"planejado", "pendente"}

    def __init__(
        self,
        solicitacoes: List[Solicitacao],
        clientes: Optional[List[Cliente]] = None,
    ) -> None:
        super().__init__()
        self._solicitacoes = [
            s for s in solicitacoes
            if s.status.lower() in self.STATUS_PENDENTES
        ]
        self._clientes = clientes
        self._cancelado = False
        self._pausado = False
        self._handler = None
        self._worker_atual: Optional[GeracaoWorker] = None

    def cancelar(self) -> None:
        """Sinaliza cancelamento de toda a fila."""
        self._cancelado = True
        if self._worker_atual:
            self._worker_atual.cancelar()

    def pausar(self, pausado: bool = True) -> None:
        """Pausa ou retoma o worker atual.

        Args:
            pausado: True para pausar.
        """
        self._pausado = pausado
        if self._worker_atual:
            self._worker_atual.pausar(pausado)

    def run(self) -> None:
        """Processa cada solicitação pendente em série."""
        total = len(self._solicitacoes)
        concluidos = 0
        erros = 0

        for idx, sol in enumerate(self._solicitacoes):
            if self._cancelado:
                break

            self.sinal_avancar.emit(idx, total)
            self.sinal_item_iniciado.emit(sol.protocolo)

            worker = GeracaoWorker(
                sol,
                handler_existente=self._handler,
                clientes=self._clientes,
            )

            imagens_capturadas: List[str] = []
            erro_capturado: Optional[str] = None
            login_bloqueou = False

            def _on_concluido(imgs, _w=worker):
                imagens_capturadas.extend(imgs)

            def _on_erro(msg):
                nonlocal erro_capturado
                erro_capturado = msg

            def _on_login():
                nonlocal login_bloqueou
                login_bloqueou = True
                self._cancelado = True

            worker.signals.concluido.connect(_on_concluido)
            worker.signals.erro.connect(_on_erro)
            worker.signals.login_necessario.connect(_on_login)
            worker.signals.login_necessario.connect(self.sinal_login_necessario)

            self._worker_atual = worker
            worker.start()
            worker.wait()

            self._handler = worker.handler

            if login_bloqueou:
                break

            if self._cancelado:
                break

            if imagens_capturadas:
                concluidos += 1
                self.sinal_item_concluido.emit(sol.protocolo, imagens_capturadas)
            else:
                erros += 1
                msg = erro_capturado or "Nenhuma imagem gerada."
                self.sinal_item_erro.emit(sol.protocolo, msg)

        self.sinal_avancar.emit(total, total)
        self.sinal_fila_concluida.emit(concluidos, erros)
