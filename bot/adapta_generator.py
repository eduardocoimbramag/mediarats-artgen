"""
Lógica de geração de artes no Adapta.org via Selenium.
"""

from __future__ import annotations

import time
import random
from pathlib import Path
from typing import Callable, List, Optional, TYPE_CHECKING

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementNotInteractableException,
    WebDriverException,
)

from bot.selenium_handler import SeleniumHandler
from bot.download_manager import DownloadManager
from utils.logger import logger
from utils.helpers import (
    backoff_espera,
    nome_arquivo_arte,
    truncar_texto,
    verificar_internet,
)

if TYPE_CHECKING:
    from excel.reader import Solicitacao


SELECTORS_LOGIN = {
    "email": [
        "input[type='email']",
        "input[name*='email' i]",
        "input[id*='email' i]",
        "input[placeholder*='e-mail' i]",
        "input[placeholder*='email' i]",
        "input[placeholder*='usuário' i]",
        "input[name*='user' i]",
    ],
    "senha": [
        "input[type='password']",
    ],
    "botao_login": [
        "button[type='submit']",
        "input[type='submit']",
        "button[class*='login' i]",
        "button[class*='entrar' i]",
        "button[class*='signin' i]",
    ],
    "erro_login": [
        "[class*='error' i]",
        "[class*='erro' i]",
        "[class*='alert' i]",
        "[class*='invalid' i]",
    ],
}

SELECTORS = {
    "campo_prompt": [
        "textarea[placeholder*='prompt' i]",
        "textarea[placeholder*='descri' i]",
        "textarea.prompt-input",
        "textarea",
        "input[type='text'][placeholder*='prompt' i]",
    ],
    "botao_gerar": [
        "button[type='submit']",
        "button:contains('Gerar')",
        "button.generate-btn",
        "button[class*='generat' i]",
        "button[class*='submit' i]",
        "input[type='submit']",
    ],
    "imagem_resultado": [
        "img.generated-image",
        "img[class*='result' i]",
        "img[class*='output' i]",
        "img[class*='generat' i]",
        ".result-image img",
        ".output img",
        "canvas",
    ],
    "indicador_carregando": [
        ".loading",
        ".spinner",
        "[class*='loading' i]",
        "[class*='spinner' i]",
        "[class*='generat' i][class*='load' i]",
    ],
    "login_form": [
        "form[action*='login' i]",
        "input[type='password']",
        "#login",
        ".login-form",
    ],
}

XPATHS = {
    "botao_gerar": [
        "//button[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'gerar')]",
        "//button[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'generate')]",
        "//button[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'criar')]",
        "//button[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'create')]",
        "//input[@type='submit']",
    ],
}


class AdaptaGenerator:
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

    def acessar_adapta(self, email: str = "", senha: str = "") -> bool:
        """Navega para o Adapta.org e verifica/realiza login.

        Tenta login automático se email e senha forem fornecidos.
        Caso contrário, deixa o navegador aberto para login manual.

        Args:
            email: E-mail de login (opcional).
            senha: Senha de login (opcional).

        Returns:
            True se autenticado e pronto para gerar.
            False se login manual for necessário (navegador permanece aberto).
        """
        logger.info("Acessando Adapta.org...")
        ok = self.handler.navegar(self.url_adapta)
        if not ok:
            return False

        time.sleep(3)

        if not self._detectar_tela_login():
            logger.sucesso("Adapta.org carregado — sessão ativa.")
            return True

        if email and senha:
            logger.info("Tela de login detectada. Tentando login automático...")
            if self.tentar_login_automatico(email, senha):
                logger.sucesso("Login automático realizado com sucesso.")
                return True
            logger.aviso("Login automático falhou. Credenciais incorretas ou página mudou.")

        logger.aviso(
            "Login necessário. Faça o login no navegador aberto e "
            "clique em 'Iniciar Geração' novamente."
        )
        self._emitir_status("login_necessario")
        return False

    def tentar_login_automatico(self, email: str, senha: str) -> bool:
        """Preenche e submete o formulário de login do Adapta.org.

        Args:
            email: E-mail de login.
            senha: Senha de login.

        Returns:
            True se o login foi bem-sucedido (saiu da tela de login).
        """
        driver = self.handler.driver
        url_antes = driver.current_url

        campo_email = None
        for sel in SELECTORS_LOGIN["email"]:
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, sel)
                for e in elems:
                    if e.is_displayed() and e.is_enabled():
                        campo_email = e
                        break
            except Exception:
                continue
            if campo_email:
                break

        campo_senha = None
        for sel in SELECTORS_LOGIN["senha"]:
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, sel)
                for e in elems:
                    if e.is_displayed() and e.is_enabled():
                        campo_senha = e
                        break
            except Exception:
                continue
            if campo_senha:
                break

        if not campo_email or not campo_senha:
            logger.aviso("Campos de e-mail/senha não localizados na página de login.")
            return False

        try:
            campo_email.clear()
            self._digitar_naturalista(campo_email, email)
            time.sleep(0.3)
            campo_senha.clear()
            self._digitar_naturalista(campo_senha, senha)
            time.sleep(0.3)

            botao = None
            for sel in SELECTORS_LOGIN["botao_login"]:
                try:
                    elems = driver.find_elements(By.CSS_SELECTOR, sel)
                    for e in elems:
                        if e.is_displayed() and e.is_enabled():
                            botao = e
                            break
                except Exception:
                    continue
                if botao:
                    break

            if botao:
                botao.click()
            else:
                campo_senha.send_keys(Keys.RETURN)

            time.sleep(4)

            if self._detectar_tela_login():
                return False
            return True

        except Exception as exc:
            logger.aviso(f"Erro durante login automático: {exc}")
            return False

    def _detectar_tela_login(self) -> bool:
        """Verifica se a página atual é de login.

        Returns:
            True se for tela de login.
        """
        for sel in SELECTORS["login_form"]:
            try:
                elems = self.handler.driver.find_elements(By.CSS_SELECTOR, sel)
                if elems:
                    return True
            except Exception:
                continue
        url = self.handler.driver.current_url.lower()
        return "login" in url or "signin" in url or "entrar" in url

    def gerar_solicitacao(self, solicitacao: "Solicitacao") -> List[Path]:
        """Gera todas as artes de uma solicitação.

        Args:
            solicitacao: Dados da solicitação com prompts e protocolo.

        Returns:
            Lista de Paths das imagens geradas com sucesso.
        """
        self._cancelado = False
        self._pausado = False

        pasta_protocolo = self.pasta_output / solicitacao.protocolo.replace("#", "_")
        pasta_protocolo.mkdir(parents=True, exist_ok=True)

        downloader = DownloadManager(pasta_protocolo, self.handler.driver)
        prompts_validos = solicitacao.prompts_validos()
        total = len(prompts_validos)

        if total == 0:
            logger.aviso(f"Nenhum prompt válido encontrado para {solicitacao.protocolo}.")
            return []

        logger.info(f"Iniciando geração de {solicitacao.protocolo} - {total} artes")
        imagens_geradas: List[Path] = []

        for idx, prompt in enumerate(prompts_validos, start=1):
            if self._cancelado:
                logger.aviso("Geração cancelada pelo usuário.")
                break

            while self._pausado:
                time.sleep(0.5)
                if self._cancelado:
                    break

            logger.info(
                f"Gerando arte {idx}/{total} - Prompt: {truncar_texto(prompt, 60)}"
            )
            self._emitir_progresso(idx - 1, total)

            nome = nome_arquivo_arte(solicitacao.protocolo, idx)
            arquivo = self._gerar_com_retry(
                prompt=prompt,
                downloader=downloader,
                nome_arquivo=nome,
                numero=idx,
                total=total,
            )

            if arquivo:
                imagens_geradas.append(arquivo)
                logger.sucesso(f"Arte {idx} baixada: {nome}")
            else:
                logger.erro(f"Arte {idx}/{total} falhou após {self.MAX_TENTATIVAS} tentativas. Pulando.")

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
    ) -> Optional[Path]:
        """Tenta gerar uma arte com retry e backoff exponencial.

        Args:
            prompt: Texto do prompt.
            downloader: Instância do DownloadManager.
            nome_arquivo: Nome do arquivo de saída.
            numero: Número da arte.
            total: Total de artes.

        Returns:
            Path do arquivo ou None se falhar.
        """
        for tentativa in range(1, self.MAX_TENTATIVAS + 1):
            if self._cancelado:
                return None
            try:
                arquivo = self._executar_geracao(prompt, downloader, nome_arquivo)
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
                    time.sleep(espera)
                    if not self.handler.ativo:
                        logger.aviso("Driver perdeu conexão, reiniciando navegador...")
                        self.handler.reiniciar()
                        self.acessar_adapta()

        return None

    def _executar_geracao(
        self, prompt: str, downloader: DownloadManager, nome_arquivo: str
    ) -> Optional[Path]:
        """Executa o fluxo de geração de uma única arte.

        Args:
            prompt: Texto do prompt.
            downloader: Instância do DownloadManager.
            nome_arquivo: Nome do arquivo de saída.

        Returns:
            Path do arquivo ou None.
        """
        driver = self.handler.driver

        campo = self._localizar_campo_prompt()
        if campo is None:
            raise NoSuchElementException("Campo de prompt não encontrado na página.")

        campo.click()
        time.sleep(0.3)
        campo.send_keys(Keys.CONTROL + "a")
        time.sleep(0.2)
        campo.clear()
        time.sleep(0.3)

        self._digitar_naturalista(campo, prompt)
        time.sleep(0.5)

        botao = self._localizar_botao_gerar()
        if botao is None:
            campo.send_keys(Keys.RETURN)
        else:
            botao.click()

        logger.info("Aguardando geração da imagem...")
        arquivo = self._aguardar_e_baixar(downloader, nome_arquivo)
        return arquivo

    def _localizar_campo_prompt(self):
        """Localiza o campo de texto de prompt na página.

        Returns:
            WebElement do campo ou None.
        """
        driver = self.handler.driver
        for sel in SELECTORS["campo_prompt"]:
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, sel)
                for elem in elems:
                    if elem.is_displayed() and elem.is_enabled():
                        return elem
            except Exception:
                continue
        return None

    def _localizar_botao_gerar(self):
        """Localiza o botão de geração na página.

        Returns:
            WebElement do botão ou None.
        """
        driver = self.handler.driver
        for xpath in XPATHS["botao_gerar"]:
            try:
                elems = driver.find_elements(By.XPATH, xpath)
                for elem in elems:
                    if elem.is_displayed() and elem.is_enabled():
                        return elem
            except Exception:
                continue
        for sel in SELECTORS["botao_gerar"]:
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, sel)
                for elem in elems:
                    if elem.is_displayed() and elem.is_enabled():
                        return elem
            except Exception:
                continue
        return None

    def _digitar_naturalista(self, elemento, texto: str, delay_min: float = 0.03, delay_max: float = 0.09) -> None:
        """Digita texto com atraso variável entre teclas, simulando humano.

        Args:
            elemento: WebElement alvo.
            texto: Texto a digitar.
            delay_min: Atraso mínimo entre teclas (segundos).
            delay_max: Atraso máximo entre teclas (segundos).
        """
        for char in texto:
            elemento.send_keys(char)
            time.sleep(random.uniform(delay_min, delay_max))

    def _aguardar_e_baixar(
        self, downloader: DownloadManager, nome_arquivo: str
    ) -> Optional[Path]:
        """Aguarda a imagem ser gerada e tenta baixá-la.

        Args:
            downloader: Instância do DownloadManager.
            nome_arquivo: Nome do arquivo de saída.

        Returns:
            Path do arquivo ou None.
        """
        driver = self.handler.driver
        inicio = time.time()
        ultimo_tamanho_imgs = 0

        while time.time() - inicio < self.timeout:
            if self._cancelado:
                return None

            self._aguardar_fim_loading(driver, espera_max=5)

            for sel in SELECTORS["imagem_resultado"]:
                try:
                    imgs = driver.find_elements(By.CSS_SELECTOR, sel)
                    imgs_validas = [
                        img for img in imgs
                        if img.is_displayed()
                        and img.get_attribute("naturalWidth")
                        and int(img.get_attribute("naturalWidth") or 0) > 100
                    ]
                    if imgs_validas:
                        arquivo = downloader.baixar_de_elemento(sel, nome_arquivo)
                        if arquivo:
                            return arquivo
                except Exception:
                    continue

            arquivo = downloader.baixar_via_js(nome_arquivo)
            if arquivo and downloader.verificar_arquivo(arquivo):
                return arquivo

            time.sleep(2)

        raise TimeoutException(f"Timeout de {self.timeout}s atingido aguardando imagem.")

    def _aguardar_fim_loading(self, driver, espera_max: int = 30) -> None:
        """Aguarda desaparecer indicadores de carregamento.

        Args:
            driver: WebDriver ativo.
            espera_max: Tempo máximo de espera.
        """
        inicio = time.time()
        while time.time() - inicio < espera_max:
            carregando = False
            for sel in SELECTORS["indicador_carregando"]:
                try:
                    elems = driver.find_elements(By.CSS_SELECTOR, sel)
                    if any(e.is_displayed() for e in elems):
                        carregando = True
                        break
                except Exception:
                    continue
            if not carregando:
                return
            time.sleep(1)
