"""
Gerenciador do Selenium WebDriver para o Media Rats - Artgen.
Detecta e inicializa o navegador disponível no sistema.
"""

from __future__ import annotations

import time
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    WebDriverException,
    TimeoutException,
    NoSuchElementException,
)
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager

from utils.logger import logger


class SeleniumHandler:
    """Controla o ciclo de vida do WebDriver.

    Args:
        headless: Se True, abre o navegador em modo headless.
        timeout: Tempo máximo de espera para elementos (segundos).
    """

    def __init__(self, headless: bool = False, timeout: int = 60) -> None:
        self.headless = headless
        self.timeout = timeout
        self._driver: Optional[webdriver.Remote] = None
        self._tipo_navegador: Optional[str] = None

    @property
    def driver(self) -> Optional[webdriver.Remote]:
        """Retorna o driver ativo."""
        return self._driver

    @property
    def ativo(self) -> bool:
        """Verifica se o driver está ativo e responsivo."""
        if self._driver is None:
            return False
        try:
            _ = self._driver.current_url
            return True
        except WebDriverException:
            return False

    def iniciar(self, max_tentativas: int = 3) -> bool:
        """Inicializa o WebDriver detectando o navegador disponível.

        Args:
            max_tentativas: Número máximo de tentativas de inicialização.

        Returns:
            True se o driver foi iniciado com sucesso.
        """
        navegadores = ["chrome", "edge", "firefox"]
        for tentativa in range(1, max_tentativas + 1):
            for nav in navegadores:
                try:
                    logger.info(f"Tentando iniciar {nav.capitalize()} (tentativa {tentativa}/{max_tentativas})...")
                    driver = self._criar_driver(nav)
                    if driver:
                        self._driver = driver
                        self._tipo_navegador = nav
                        logger.sucesso(f"Navegador {nav.capitalize()} iniciado com sucesso.")
                        return True
                except Exception as exc:
                    logger.aviso(f"Falha ao iniciar {nav}: {exc}")
                    continue
            if tentativa < max_tentativas:
                logger.aviso(f"Todos os navegadores falharam. Aguardando antes de tentar novamente...")
                time.sleep(3)

        logger.erro("Não foi possível iniciar nenhum navegador após todas as tentativas.")
        return False

    def _criar_driver(self, navegador: str) -> Optional[webdriver.Remote]:
        """Cria instância do driver para o navegador especificado.

        Args:
            navegador: Nome do navegador ('chrome', 'firefox', 'edge').

        Returns:
            Driver configurado ou None se falhar.
        """
        if navegador == "chrome":
            opts = ChromeOptions()
            if self.headless:
                opts.add_argument("--headless=new")
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")
            opts.add_argument("--disable-blink-features=AutomationControlled")
            opts.add_experimental_option("excludeSwitches", ["enable-automation"])
            opts.add_experimental_option("useAutomationExtension", False)
            opts.add_argument("--window-size=1280,900")
            service = ChromeService(ChromeDriverManager().install())
            return webdriver.Chrome(service=service, options=opts)

        elif navegador == "firefox":
            opts = FirefoxOptions()
            if self.headless:
                opts.add_argument("--headless")
            opts.set_preference("dom.webdriver.enabled", False)
            service = FirefoxService(GeckoDriverManager().install())
            return webdriver.Firefox(service=service, options=opts)

        elif navegador == "edge":
            opts = EdgeOptions()
            if self.headless:
                opts.add_argument("--headless=new")
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")
            opts.add_argument("--window-size=1280,900")
            service = EdgeService(EdgeChromiumDriverManager().install())
            return webdriver.Edge(service=service, options=opts)

        return None

    def navegar(self, url: str) -> bool:
        """Navega para uma URL.

        Args:
            url: URL de destino.

        Returns:
            True se a navegação foi bem-sucedida.
        """
        if not self.ativo:
            logger.erro("Driver não está ativo para navegação.")
            return False
        try:
            self._driver.get(url)
            logger.info(f"Navegando para: {url}")
            return True
        except WebDriverException as exc:
            logger.erro(f"Erro ao navegar para {url}: {exc}")
            return False

    def esperar_elemento(
        self,
        seletor: str,
        tipo: str = "css",
        timeout: Optional[int] = None,
    ):
        """Aguarda e retorna um elemento da página.

        Args:
            seletor: Seletor CSS ou XPath.
            tipo: 'css' ou 'xpath'.
            timeout: Tempo de espera em segundos (usa padrão se None).

        Returns:
            WebElement encontrado.

        Raises:
            TimeoutException: Se o elemento não aparecer no tempo limite.
        """
        t = timeout or self.timeout
        by = By.CSS_SELECTOR if tipo == "css" else By.XPATH
        wait = WebDriverWait(self._driver, t)
        return wait.until(EC.presence_of_element_located((by, seletor)))

    def esperar_clicavel(
        self,
        seletor: str,
        tipo: str = "css",
        timeout: Optional[int] = None,
    ):
        """Aguarda elemento clicável.

        Args:
            seletor: Seletor CSS ou XPath.
            tipo: 'css' ou 'xpath'.
            timeout: Tempo de espera em segundos.

        Returns:
            WebElement clicável.
        """
        t = timeout or self.timeout
        by = By.CSS_SELECTOR if tipo == "css" else By.XPATH
        wait = WebDriverWait(self._driver, t)
        return wait.until(EC.element_to_be_clickable((by, seletor)))

    def fechar(self) -> None:
        """Fecha o navegador e encerra o driver."""
        if self._driver:
            try:
                self._driver.quit()
                logger.info("Navegador fechado.")
            except WebDriverException:
                pass
            finally:
                self._driver = None
                self._tipo_navegador = None

    def reiniciar(self) -> bool:
        """Fecha e reabre o navegador.

        Returns:
            True se o reinício foi bem-sucedido.
        """
        logger.aviso("Reiniciando navegador...")
        self.fechar()
        time.sleep(2)
        return self.iniciar()

    def verificar_login(self, url_base: str) -> Optional[bool]:
        """Verifica se o usuário está logado na página atual.
        Retorna None se não for possível determinar.

        Args:
            url_base: URL base do site para verificação.

        Returns:
            True se logado, False se não logado, None se indeterminado.
        """
        if not self.ativo:
            return None
        current = self._driver.current_url
        if "login" in current.lower() or "signin" in current.lower():
            return False
        return None

    def screenshot(self, caminho: str) -> bool:
        """Tira screenshot da página atual.

        Args:
            caminho: Caminho onde salvar o arquivo .png.

        Returns:
            True se capturado com sucesso.
        """
        if not self.ativo:
            return False
        try:
            self._driver.save_screenshot(caminho)
            return True
        except WebDriverException:
            return False
