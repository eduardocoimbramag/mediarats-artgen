"""
Lógica de geração de artes no Adapta.org via Selenium.

Orquestrador principal. As responsabilidades foram separadas em:
- bot.selectors      — dicionários de seletores CSS/XPath
- bot.login_handler  — AdaptaLoginMixin: autenticação no Adapta.org
- bot.chat_handler   — AdaptaChatMixin: navegação de chats e pastas
- bot.image_detector — AdaptaImageMixin: compositor, prompt e download
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, List, Optional, TYPE_CHECKING

from selenium.common.exceptions import NoSuchElementException

from bot.selenium_handler import SeleniumHandler
from bot.download_manager import DownloadManager
from bot.login_handler import AdaptaLoginMixin
from bot.chat_handler import AdaptaChatMixin
from bot.image_detector import AdaptaImageMixin
from utils.logger import logger
from utils.helpers import (
    backoff_espera,
    nome_arquivo_arte,
    truncar_texto,
    verificar_internet,
)
from utils.prompt_composer import compor_prompt_arte, PerfilCliente

if TYPE_CHECKING:
    from excel.reader import Cliente, Solicitacao


class AdaptaGenerator(AdaptaLoginMixin, AdaptaChatMixin, AdaptaImageMixin):
    """Automatiza a geração de imagens no Adapta.org.

    Args:
        handler: Instância do SeleniumHandler com driver ativo.
        url_adapta: URL base do Adapta.org.
        pasta_output: Pasta base para salvar os arquivos.
        timeout: Timeout de espera para geração em segundos.
    """

    MAX_TENTATIVAS = 3

    def __init__(
        self,
        handler: SeleniumHandler,
        url_adapta: str,
        pasta_output: Path,
        timeout: int = 60,
    ) -> None:
        self.handler = handler
        self.url_adapta = url_adapta.rstrip("/")
        self.pasta_output = Path(pasta_output)
        self.timeout = timeout
        self._cancelado = False
        self._pausado = False
        self._progresso_callback: Optional[Callable[[int, int], None]] = None
        self._status_callback: Optional[Callable[[str], None]] = None
        self._solicitacao_ativa: Optional["Solicitacao"] = None

    def definir_callbacks(
        self,
        progresso: Optional[Callable[[int, int], None]] = None,
        status: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Define callbacks para comunicação com a GUI.

        Args:
            progresso: fn(atual, total) chamada ao avançar no progresso.
            status: fn(mensagem) chamada para atualizações de status.
        """
        self._progresso_callback = progresso
        self._status_callback = status

    def cancelar(self) -> None:
        """Sinaliza cancelamento da geração."""
        self._cancelado = True

    def pausar(self, pausado: bool = True) -> None:
        """Pausa ou retoma a geração.

        Args:
            pausado: True para pausar, False para retomar.
        """
        self._pausado = pausado

    def _emitir_progresso(self, atual: int, total: int) -> None:
        if self._progresso_callback:
            try:
                self._progresso_callback(atual, total)
            except Exception:
                pass

    def _emitir_status(self, msg: str) -> None:
        if self._status_callback:
            try:
                self._status_callback(msg)
            except Exception:
                pass

    def _aguardar(self, segundos: float) -> None:
        """Aguarda pelo tempo indicado verificando cancelamento a cada 0.1s.

        Substitui ``time.sleep()`` em esperas longas para que o cancelamento
        seja responsivo mesmo durante waits de vários segundos.

        Args:
            segundos: Tempo total de espera em segundos.
        """
        fim = time.monotonic() + segundos
        while time.monotonic() < fim:
            if self._cancelado:
                return
            time.sleep(0.1)

    def verificar_prerequisitos(self) -> bool:
        """Verifica internet e disponibilidade do driver.

        Returns:
            True se tudo estiver OK.
        """
        if not verificar_internet():
            logger.erro("Sem conexão com a internet. Verifique sua rede.")
            return False
        if not self.handler.ativo:
            logger.erro("Driver do navegador não está ativo.")
            return False
        return True


    def gerar_solicitacao(
        self,
        solicitacao: "Solicitacao",
        cliente: Optional["Cliente"] = None,
    ) -> List[Path]:
        """Gera todas as artes de uma solicitação.

        A composição do prompt final é centralizada em
        ``utils.prompt_composer.compor_prompt_arte()`` — cada arte recebe
        um prompt composto que inclui perfil do cliente, tema, instrução
        principal e variações complementares da série.

        Args:
            solicitacao: Dados da solicitação com prompts e protocolo.
            cliente: Dados cadastrais do cliente (perfil). Quando fornecido,
                     o perfil é injetado em cada prompt enviado ao chat.

        Returns:
            Lista de Paths das imagens geradas com sucesso.
        """
        self._cancelado = False
        self._pausado = False
        self._solicitacao_ativa = solicitacao

        perfil = PerfilCliente.from_cliente(cliente) if cliente else PerfilCliente()
        if perfil.vazio:
            logger.aviso(
                f"[Composer] Perfil do cliente '{solicitacao.codigo_cliente}' "
                "está vazio ou incompleto — prompt será gerado sem contexto de marca."
            )
        else:
            logger.info(
                f"[Composer] Perfil carregado: {perfil.nome} ({perfil.codigo}) "
                f"| nicho={perfil.nicho or '—'} | estilo={perfil.estilo_visual or '—'}"
            )

        pasta_protocolo = self.pasta_output / solicitacao.protocolo.replace("#", "_")
        pasta_protocolo.mkdir(parents=True, exist_ok=True)

        downloader = DownloadManager(pasta_protocolo, self.handler.driver)
        prompts_validos = solicitacao.prompts_validos()
        total = len(prompts_validos)

        if total == 0:
            logger.aviso(f"Nenhum prompt válido encontrado para {solicitacao.protocolo}.")
            return []

        self.resolver_chat_cliente(solicitacao.codigo_cliente, solicitacao.cliente)

        logger.info(f"Iniciando geração de {solicitacao.protocolo} — {total} arte(s)")
        imagens_geradas: List[Path] = []

        # Conjunto global de URLs já baixadas neste ciclo — garante deduplicação
        # mesmo que o Adapta gere múltiplas imagens numa única resposta.
        urls_baixadas: set = set()

        for idx, prompt_bruto in enumerate(prompts_validos, start=1):
            if self._cancelado:
                logger.aviso("Geração cancelada pelo usuário.")
                break

            while self._pausado:
                time.sleep(0.5)
                if self._cancelado:
                    break

            # ── CORREÇÃO C1: prompt AUTOCONTIDO — sem variações de outras artes ──
            # Cada arte recebe apenas seu próprio prompt + perfil + tema.
            # Não passamos a lista completa de prompts como 'variacoes',
            # pois isso causava o Adapta a gerar N imagens por mensagem.
            prompt_composto = compor_prompt_arte(
                perfil=perfil,
                tema=solicitacao.tema,
                prompt_principal=prompt_bruto,
                numero_arte=idx,
                total_artes=total,
            )

            logger.info(
                f"[Arte {idx}/{total}] Prompt individual composto com sucesso "
                f"({len(prompt_composto)} chars): {truncar_texto(prompt_bruto, 60)!r}"
            )
            self._emitir_progresso(idx - 1, total)

            # ── CORREÇÃO C4: snapshot ANTES do envio ──
            snapshot_antes = self._tirar_snapshot_imagens()
            logger.info(
                f"[Arte {idx}/{total}] Snapshot antes do envio: "
                f"{len(snapshot_antes)} img(s) conhecida(s). "
                f"Já baixadas no ciclo: {len(urls_baixadas)}."
            )

            nome = nome_arquivo_arte(solicitacao.protocolo, idx)
            arquivo = self._gerar_com_retry(
                prompt=prompt_composto,
                downloader=downloader,
                nome_arquivo=nome,
                numero=idx,
                total=total,
                snapshot_antes=snapshot_antes,
                urls_baixadas=urls_baixadas,
            )

            if arquivo:
                imagens_geradas.append(arquivo)
                logger.sucesso(f"[Arte {idx}/{total}] Concluída com sucesso: {nome}")
                # ── C9: aguardar SPA estabilizar após resposta ──
                # Evita que a arte seguinte snapshote ou envie enquanto o Adapta
                # ainda está re-renderizando a UI (ex: criando novo chat, reload).
                if idx < total:
                    self._aguardar_estabilizacao_spa(
                        arte_label=f"Arte {idx}/{total}",
                        timeout_s=8,
                    )
            else:
                logger.erro(
                    f"[Arte {idx}/{total}] Falhou após {self.MAX_TENTATIVAS} tentativas. Pulando."
                )

        self._emitir_progresso(total, total)
        logger.sucesso(
            f"Geração de {solicitacao.protocolo} CONCLUÍDA! "
            f"{len(imagens_geradas)}/{total} artes salvas em {pasta_protocolo}"
        )
        return imagens_geradas

    def _gerar_com_retry(
        self,
        prompt: str,
        downloader: DownloadManager,
        nome_arquivo: str,
        numero: int,
        total: int,
        snapshot_antes: Optional[set] = None,
        urls_baixadas: Optional[set] = None,
    ) -> Optional[Path]:
        """Tenta gerar uma arte com retry e backoff exponencial.

        Args:
            prompt: Texto do prompt.
            downloader: Instância do DownloadManager.
            nome_arquivo: Nome do arquivo de saída.
            numero: Número da arte.
            total: Total de artes.
            snapshot_antes: URLs de imagens conhecidas antes do envio.
            urls_baixadas: Conjunto compartilhado de URLs já baixadas no ciclo.

        Returns:
            Path do arquivo ou None se falhar.
        """
        _snapshot = snapshot_antes if snapshot_antes is not None else set()
        _urls_baixadas = urls_baixadas if urls_baixadas is not None else set()

        for tentativa in range(1, self.MAX_TENTATIVAS + 1):
            if self._cancelado:
                return None
            try:
                arquivo = self._executar_geracao(
                    prompt, downloader, nome_arquivo,
                    snapshot_antes=_snapshot,
                    urls_baixadas=_urls_baixadas,
                    numero_arte=numero,
                    total_artes=total,
                )
                if arquivo and downloader.verificar_arquivo(arquivo):
                    return arquivo
                raise ValueError("Arquivo inválido ou não gerado.")
            except Exception as exc:
                logger.aviso(
                    f"Tentativa {tentativa}/{self.MAX_TENTATIVAS} falhou: {exc}"
                )
                if tentativa < self.MAX_TENTATIVAS:
                    espera = backoff_espera(tentativa)
                    logger.info(f"Aguardando {espera:.0f}s antes de tentar novamente...")
                    self._aguardar(espera)
                    if not self.handler.ativo:
                        logger.aviso("Driver perdeu conexão, reiniciando navegador...")
                        self.handler.reiniciar()
                        from utils.config import Config as _Cfg
                        self.acessar_adapta(
                            email=_Cfg.ADAPTA_EMAIL,
                            senha=_Cfg.ADAPTA_SENHA,
                        )
                        if self._solicitacao_ativa:
                            self.resolver_chat_cliente(
                                self._solicitacao_ativa.codigo_cliente,
                                self._solicitacao_ativa.cliente,
                            )

        return None

    def _executar_geracao(
        self,
        prompt: str,
        downloader: DownloadManager,
        nome_arquivo: str,
        snapshot_antes: Optional[set] = None,
        urls_baixadas: Optional[set] = None,
        numero_arte: int = 0,
        total_artes: int = 0,
    ) -> Optional[Path]:
        """Executa o fluxo de geração de uma única arte.

        Fluxo:
            1. Aguarda compositor ficar disponível (15s).
            2. Scroll + foco explícito.
            3. Limpa o campo.
            4. Insere o prompt ATOMICAMENTE via JS (sem char-by-char, sem \\n como Enter).
            5. Envia: botão (máx 3s) → Enter como fallback imediato.
            6. Aguarda imagem NOVA (não presente no snapshot) e baixa com deduplicação.

        Args:
            prompt: Texto do prompt composto.
            downloader: Instância do DownloadManager.
            nome_arquivo: Nome do arquivo de saída.
            snapshot_antes: URLs de imagens conhecidas antes do envio.
            urls_baixadas: Conjunto compartilhado de URLs já baixadas no ciclo.
            numero_arte: Número sequencial desta arte.
            total_artes: Total de artes no protocolo.

        Returns:
            Path do arquivo gerado ou None.

        Raises:
            NoSuchElementException: Se o compositor não for encontrado.
        """
        driver = self.handler.driver
        t_inicio = time.time()

        logger.info(
            f"[Composer] Aguardando compositor ({len(prompt)} chars)..."
        )
        campo = self._aguardar_compositor(timeout_s=15)
        if campo is None:
            raise NoSuchElementException(
                "Campo de prompt não encontrado na página após 15s. "
                "Verifique os logs [Composer][Diagnóstico] para detalhes."
            )

        tag = campo.tag_name
        ce = campo.get_attribute("contenteditable") or ""
        tipo = f"{tag}[contenteditable=true]" if ce == "true" else tag
        logger.info(f"[Composer] Compositor pronto: tipo='{tipo}'.")

        # Scroll + foco
        try:
            driver.execute_script(
                "arguments[0].scrollIntoView({block:'center',inline:'center'});",
                campo,
            )
            time.sleep(0.3)
        except Exception:
            pass
        try:
            driver.execute_script("arguments[0].click();", campo)
        except Exception:
            try:
                campo.click()
            except Exception:
                pass
        time.sleep(0.2)
        try:
            driver.execute_script("arguments[0].focus();", campo)
            time.sleep(0.2)
        except Exception:
            pass

        # Limpar
        self._limpar_campo_compositor(campo)
        time.sleep(0.2)

        # Inserir prompt atomicamente (sem char-by-char, sem \n como Enter)
        arte_label = f"Arte {numero_arte}/{total_artes}" if numero_arte else "Arte"
        ok = self._inserir_prompt_compositor(campo, prompt)
        if not ok:
            logger.aviso(
                f"[{arte_label}] Inserção reportou problema — continuando mesmo assim."
            )
        else:
            logger.info(f"[{arte_label}] Prompt inserido no composer com sucesso.")
        time.sleep(0.3)

        # ── Enviar com confirmação real ──
        # NUNCA trata tentativa de envio como sucesso automático.
        # Só avança para download após prova concreta de que a mensagem saiu.
        metodo, envio_confirmado = self._enviar_prompt_compositor(
            campo,
            texto_inserido=prompt,
            arte_label=arte_label,
        )

        logger.info(
            f"[{arte_label}] Envio confirmado? "
            f"{'SIM' if envio_confirmado else 'NÃO'} "
            f"(método: '{metodo}', tempo total: {time.time() - t_inicio:.1f}s)."
        )

        if not envio_confirmado:
            logger.erro(
                f"[{arte_label}] Download NÃO iniciado — envio não foi confirmado. "
                f"Prompt pode estar parado no composer. Acionando retry."
            )
            raise ValueError(
                f"[{arte_label}] Envio NÃO confirmado via '{metodo}'. "
                f"Texto permaneceu no compositor. Abortando para retry."
            )

        logger.info(
            f"[{arte_label}] Monitoramento de imagem iniciado apenas após envio confirmado."
        )
        arquivo = self._aguardar_e_baixar(
            downloader,
            nome_arquivo,
            snapshot_antes=snapshot_antes if snapshot_antes is not None else set(),
            urls_baixadas=urls_baixadas if urls_baixadas is not None else set(),
            numero_arte=numero_arte,
            total_artes=total_artes,
        )
        return arquivo

