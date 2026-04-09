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
from utils.prompt_composer import compor_prompt_arte, PerfilCliente

if TYPE_CHECKING:
    from excel.reader import Cliente, Solicitacao


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
        # --- Modern chat composers: contenteditable divs ---
        "div[contenteditable='true']",
        "p[contenteditable='true']",
        "[contenteditable='true']",
        # --- Textarea com placeholders comuns em chat/AI ---
        "textarea[placeholder*='prompt' i]",
        "textarea[placeholder*='descri' i]",
        "textarea[placeholder*='mensa' i]",
        "textarea[placeholder*='escrev' i]",
        "textarea[placeholder*='digi' i]",
        "textarea[placeholder*='pergunt' i]",
        "textarea.prompt-input",
        "textarea",
        # --- Input text (menos comum em compositors de chat) ---
        "input[type='text'][placeholder*='prompt' i]",
        "input[type='text'][placeholder*='mensa' i]",
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


SELECTORS_PROJETO = {
    "sidebar": [
        "nav", "aside", "[class*='sidebar' i]", "[id*='sidebar' i]",
        "[role='navigation']", "[class*='panel' i]", "[class*='drawer' i]",
    ],
    "item_pasta": [
        "[class*='folder' i]", "[class*='project' i]", "[class*='group' i]",
        "[class*='category' i]", "[class*='collection' i]",
        "[data-type='folder']", "[data-type='project']",
    ],
    "item_chat": [
        "a[href*='/chat/']", "a[href*='/conversation/']", "a[href*='/c/']",
        "[class*='chat-item']", "[class*='conversation']",
        "[data-type='chat']", "[data-type='conversation']",
        "li > a", "li[class*='item'] > a",
    ],
    "botao_novo_chat": [
        "button[aria-label*='new chat' i]", "button[aria-label*='novo chat' i]",
        "button[aria-label*='nova conversa' i]", "button[aria-label*='criar' i]",
        "[data-testid*='new-chat' i]", "[data-testid*='novo-chat' i]",
        "button[class*='new-chat' i]", "a[class*='new-chat' i]",
        "button[class*='create' i]", "[title*='new chat' i]",
        "[title*='novo chat' i]", "[title*='nova conversa' i]",
        "[data-action='new-chat']", "[data-action='create-chat']",
    ],
    "titulo_chat": [
        "input[autofocus]", "input[class*='title' i]", "input[class*='name' i]",
        "input[placeholder*=\'t\u00edtulo\' i]", "input[placeholder*='title' i]",
        "input[placeholder*='nome' i]", "textarea[class*='title' i]",
        "[contenteditable='true']",
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
        """Navega para o AdaptaOne e verifica/realiza login.

        Após login bem-sucedido, navega automaticamente para a seção
        "ADAPTA one" (Chat com IAs premium) para que o prompt field
        seja encontrado na etapa de geração.

        Lógica de login:
            1. Se não há tela de login → sessão ativa, prossegue.
            2. Se há tela de login E credenciais estão configuradas →
               tenta login automático primeiro.
            3. Se login automático falha → emite ``login_falhou``.
            4. Se credenciais não estão configuradas → emite
               ``login_necessario``.

        Args:
            email: E-mail de login (opcional).
            senha: Senha de login (opcional).

        Returns:
            True se autenticado e dentro da interface de chat.
            False se login manual for necessário (navegador permanece aberto).
        """
        logger.info("Acessando AdaptaOne...")
        ok = self.handler.navegar(self.url_adapta)
        if not ok:
            return False

        time.sleep(3)

        if not self._detectar_tela_login():
            logger.sucesso("AdaptaOne carregado — sessão ativa.")
            self._navegar_para_adapta_one()
            return True

        tem_credenciais = bool(email and email.strip() and senha and senha.strip())

        if tem_credenciais:
            logger.info("Tela de login detectada. Login automático configurado — tentando...")
            if self.tentar_login_automatico(email, senha):
                logger.sucesso("Login automático realizado com sucesso.")
                self._navegar_para_adapta_one()
                return True
            logger.aviso(
                "Login automático falhou. Verifique as credenciais configuradas "
                "ou faça login manualmente no navegador."
            )
            self._emitir_status("login_falhou")
            return False

        logger.aviso(
            "Login manual necessário — credenciais de login automático não configuradas. "
            "Faça login no navegador e clique em 'Iniciar Geração' novamente."
        )
        self._emitir_status("login_necessario")
        return False

    def _esta_no_dashboard(self) -> bool:
        """Verifica se a página atual é o dashboard do AdaptaOne (não um chat).

        Usa dois sinais em ordem de confiabilidade:
        1. URL idêntica à raiz/dashboard (mais confiável).
        2. Presença visível de 'Acesso Rápido' — seção exclusiva do dashboard.
           Não usamos 'Chat com IAs' nem 'ADAPTAONE' pois podem aparecer no
           sidebar mesmo dentro da interface de chat.

        Returns:
            True se estiver no dashboard/menu inicial.
        """
        driver = self.handler.driver
        url_atual = driver.current_url.rstrip("/")
        base = self.url_adapta.rstrip("/")

        if url_atual == base or url_atual == base + "/dashboard":
            return True

        for texto in ("Acesso Rápido", "Acesso Rapido"):
            try:
                elems = driver.find_elements(
                    By.XPATH,
                    f".//*[contains(normalize-space(.), '{texto}')]"
                )
                if any(e.is_displayed() for e in elems):
                    return True
            except Exception:
                continue

        return False

    def _navegar_para_adapta_one(self) -> bool:
        """Clica no card 'ADAPTA one' no dashboard para entrar no chat.

        Só age se o dashboard estiver visível. Se já estiver dentro
        de uma página de chat, retorna True imediatamente sem clicar.

        Returns:
            True se a navegação foi bem-sucedida ou já estava no chat.
        """
        if not self._esta_no_dashboard():
            logger.info("[AdaptaOne] Já dentro da interface de chat.")
            return True

        driver = self.handler.driver
        logger.info("[AdaptaOne] Dashboard detectado. Clicando em 'ADAPTA one'...")

        xpaths_card = [
            ".//*[contains(normalize-space(text()), 'Chat com IAs')]",
            ".//*[contains(normalize-space(text()), 'Chat com IAs premium')]",
            ".//h2[contains(normalize-space(text()), 'one')]",
            ".//h3[contains(normalize-space(text()), 'one')]",
            ".//*[contains(@class, 'card')][contains(normalize-space(.), 'one')]",
            ".//*[contains(@class, 'item')][contains(normalize-space(.), 'one')]",
            ".//a[contains(normalize-space(.), 'one')]",
        ]

        for xpath in xpaths_card:
            try:
                elems = driver.find_elements(By.XPATH, xpath)
                for elem in elems:
                    if not elem.is_displayed():
                        continue
                    try:
                        clickable = elem
                        parent = elem.find_element(By.XPATH, "./ancestor-or-self::a | ./ancestor-or-self::button")
                        if parent and parent.is_displayed():
                            clickable = parent
                    except Exception:
                        pass
                    try:
                        driver.execute_script("arguments[0].click();", clickable)
                        time.sleep(3)
                        if not self._esta_no_dashboard():
                            logger.sucesso("[AdaptaOne] Entrou na interface de chat com sucesso.")
                            return True
                    except Exception:
                        continue
            except Exception:
                continue

        logger.aviso(
            "[AdaptaOne] Não foi possível clicar no card 'ADAPTA one' automaticamente. "
            "Verifique se o layout da página mudou."
        )
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

    def resolver_chat_cliente(self, codigo_cliente: str, nome_cliente: str) -> bool:
        """Garante que o navegador está posicionado no chat canônico do cliente.

        Regra: 1 chat por cliente dentro da pasta NOME_PASTA_PROJETO.

        Fluxo determinístico:
            1. Consulta chat_mapping.json pelo código do cliente.
            2. Se URL registrada: navega para ela e valida.
            3. Se URL inválida (chat deletado): remove o vínculo e rebusca.
            4. Busca na lista de chats por título contendo código/nome.
            5. Se não encontrar: cria novo chat e persiste o vínculo.

        Proteção contra duplicatas:
            set_chat_url() usa first-write-wins — nunca sobrescreve um vínculo
            existente; forcar_chat_url() é usado apenas quando o original falhou.

        Args:
            codigo_cliente: Código único do cliente (ex: DUDE).
            nome_cliente: Nome legível para nomear/encontrar o chat.

        Returns:
            True se o chat foi resolvido com sucesso.
        """
        from bot.chat_mapping import chat_mapping

        titulo_esperado = self._titulo_chat_para_cliente(codigo_cliente, nome_cliente)
        logger.info(f"[Chat] Resolvendo chat: '{titulo_esperado}'...")

        self._navegar_pasta_projeto()

        url_existente = chat_mapping.get_chat_url(codigo_cliente)
        if url_existente:
            logger.info(f"[Chat] Vínculo registrado: {url_existente}")
            if self._navegar_para_chat(url_existente):
                logger.sucesso(f"[Chat] ✓ Chat do cliente '{codigo_cliente}' reutilizado.")
                return True
            logger.aviso("[Chat] URL registrada inválida. Removendo vínculo e rebuscando...")
            chat_mapping.remover(codigo_cliente)

        url_encontrada = self._buscar_chat_na_lista(codigo_cliente, nome_cliente)
        if url_encontrada:
            chat_mapping.forcar_chat_url(codigo_cliente, url_encontrada, titulo_esperado)
            logger.sucesso(f"[Chat] ✓ Chat encontrado na lista: {url_encontrada}")
            return True

        logger.info(f"[Chat] Criando novo chat para '{titulo_esperado}'...")
        url_novo = self._criar_novo_chat(codigo_cliente, nome_cliente)
        if url_novo:
            chat_mapping.set_chat_url(codigo_cliente, url_novo, titulo_esperado)
            logger.sucesso(f"[Chat] ✓ Novo chat criado: {url_novo}")
            return True

        logger.aviso(
            f"[Chat] ✗ Não foi possível resolver chat para '{codigo_cliente}'. "
            "Continuando na página atual."
        )
        return False

    def _navegar_pasta_projeto(self) -> bool:
        """Clica na pasta do projeto no sidebar para contextualizar os chats.

        Busca por texto exato de NOME_PASTA_PROJETO em elementos clicáveis
        do sidebar. Falha silenciosamente para não bloquear a geração.

        Returns:
            True se a pasta foi localizada e clicada.
        """
        from utils.config import Config
        nome_pasta = Config.NOME_PASTA_PROJETO
        driver = self.handler.driver

        logger.info(f"[Chat] Buscando pasta '{nome_pasta}' no sidebar...")

        xpaths = [
            f".//*[normalize-space(text())='{nome_pasta}']",
            f".//*[contains(normalize-space(text()), '{nome_pasta}')]",
            f".//*[contains(normalize-space(.), '{nome_pasta}')]",
        ]

        for xpath in xpaths:
            try:
                elems = driver.find_elements(By.XPATH, xpath)
                for elem in elems:
                    tag = elem.tag_name.lower()
                    if tag not in ("a", "button", "li", "div", "span", "p"):
                        continue
                    if not elem.is_displayed():
                        continue
                    try:
                        driver.execute_script("arguments[0].click();", elem)
                        time.sleep(1.5)
                        logger.info(f"[Chat] Pasta '{nome_pasta}' acessada.")
                        return True
                    except Exception:
                        continue
            except Exception:
                continue

        logger.aviso(f"[Chat] Pasta '{nome_pasta}' não localizada no sidebar.")
        return False

    def _navegar_para_chat(self, url: str) -> bool:
        """Navega para a URL de um chat e verifica se chegou corretamente.

        Além de checar a URL, valida que a página possui um campo de prompt
        funcional (textarea/input). Se o chat foi deletado manualmente no
        Adapta, a página pode carregar mas sem compositor — isso é tratado
        como chat inválido.

        Args:
            url: URL completa do chat armazenada no mapeamento.

        Returns:
            True se a navegação resultou em uma página de chat válida
            com compositor funcional.
        """
        driver = self.handler.driver
        try:
            driver.get(url)
            time.sleep(3)
        except Exception as exc:
            logger.aviso(f"[Chat] Falha ao navegar para {url}: {exc}")
            return False

        url_atual = driver.current_url

        if self._detectar_tela_login():
            logger.aviso("[Chat] Redirecionado para login — sessão expirou.")
            return False

        if url_atual.rstrip("/") in (self.url_adapta, self.url_adapta + "/"):
            logger.aviso("[Chat] Redirecionado para homepage — chat pode ter sido deletado.")
            return False

        if self._esta_no_dashboard():
            logger.aviso("[Chat] Redirecionado para dashboard — chat removido ou inacessível.")
            return False

        if not self._e_url_de_chat_valida(url_atual):
            logger.aviso(f"[Chat] URL resultante não é de chat: {url_atual}")
            return False

        if not self._verificar_compositor_presente():
            logger.aviso(
                "[Chat] Chat carregado mas sem campo de prompt funcional — "
                "chat removido ou inconsistente."
            )
            return False

        logger.info("[Chat] Chat validado — compositor funcional encontrado.")
        return True

    def _verificar_compositor_presente(self, tentativas: int = 2) -> bool:
        """Verifica se a página atual possui um campo de prompt funcional.

        Usa `_aguardar_compositor` com timeout baseado no número de tentativas.
        Detecta corretamente tanto textarea quanto div[contenteditable='true'].

        Args:
            tentativas: Quantidade de ciclos de 2s de espera (total = tentativas*2s).

        Returns:
            True se um compositor válido foi encontrado e está visível.
        """
        timeout_s = max(tentativas * 2, 4)
        campo = self._aguardar_compositor(timeout_s=timeout_s)
        if campo is not None:
            logger.info("[Chat] Compositor presente e validado na página.")
            return True
        logger.aviso("[Chat] Compositor não encontrado — chat removido ou inacessível.")
        return False

    def _e_url_de_chat_valida(self, url: str) -> bool:
        """Verifica heuristicamente se uma URL corresponde a um chat ativo.

        Args:
            url: URL a verificar.

        Returns:
            True se a URL parece ser de um chat (tem path além da raiz e não é login).
        """
        if not url:
            return False
        url_lower = url.lower()
        for palavra in ("login", "signin", "entrar", "register", "cadastro"):
            if palavra in url_lower:
                return False
        base = self.url_adapta.rstrip("/")
        path = url.rstrip("/")[len(base):].lstrip("/")
        return len(path) > 2

    def _buscar_chat_na_lista(self, codigo_cliente: str, nome_cliente: str) -> Optional[str]:
        """Procura na lista de chats do sidebar um chat cujo título contenha o cliente.

        Estratégia de busca em ordem de prioridade:
            1. Link contendo o código do cliente (mais específico)
            2. Link contendo o nome do cliente

        Args:
            codigo_cliente: Código do cliente (ex: DUDE).
            nome_cliente: Nome do cliente.

        Returns:
            URL do chat encontrado, ou None.
        """
        driver = self.handler.driver
        termos = [t for t in [codigo_cliente.strip(), nome_cliente.strip()] if t]

        for termo in termos:
            xpaths = [
                f"//a[contains(normalize-space(.), '{termo}')]",
                f"//*[contains(normalize-space(text()), '{termo}')]/ancestor-or-self::a",
                f"//*[contains(normalize-space(.), '{termo}')]/ancestor-or-self::a[@href]",
            ]
            for xpath in xpaths:
                try:
                    elems = driver.find_elements(By.XPATH, xpath)
                    for elem in elems:
                        if not elem.is_displayed():
                            continue
                        href = elem.get_attribute("href") or ""
                        if href and self._e_url_de_chat_valida(href):
                            logger.info(f"[Chat] Chat encontrado por '{termo}': {href}")
                            try:
                                driver.execute_script("arguments[0].click();", elem)
                                time.sleep(2)
                                url_atual = driver.current_url
                                if self._e_url_de_chat_valida(url_atual):
                                    return url_atual
                            except Exception:
                                return href
                except Exception:
                    continue

        return None

    def _criar_novo_chat(self, codigo_cliente: str, nome_cliente: str) -> Optional[str]:
        """Cria um novo chat no Adapta.org e retorna sua URL.

        Clica no botão de novo chat, aguarda a navegação e tenta
        renomear o chat com o título padronizado do cliente.

        Args:
            codigo_cliente: Código do cliente.
            nome_cliente: Nome do cliente para o título do chat.

        Returns:
            URL do chat criado, ou None se a criação falhar.
        """
        driver = self.handler.driver
        url_antes = driver.current_url

        botao = self._localizar_botao_novo_chat()
        if botao is None:
            logger.aviso("[Chat] Botão 'novo chat' não encontrado.")
            return None

        try:
            driver.execute_script("arguments[0].click();", botao)
            time.sleep(3)
        except Exception as exc:
            logger.aviso(f"[Chat] Falha ao clicar 'novo chat': {exc}")
            return None

        url_novo = driver.current_url
        if url_novo.rstrip("/") == url_antes.rstrip("/"):
            time.sleep(2)
            url_novo = driver.current_url

        if not self._e_url_de_chat_valida(url_novo):
            logger.aviso(f"[Chat] URL após criar chat não é válida: {url_novo}")
            return None

        logger.info(f"[Chat] Novo chat aberto em: {url_novo}")
        titulo = self._titulo_chat_para_cliente(codigo_cliente, nome_cliente)
        self._renomear_chat(titulo)

        logger.info(
            "[Chat] Rename concluído. Aguardando compositor ficar pronto "
            "para envio de prompt..."
        )
        campo = self._aguardar_compositor(timeout_s=12)
        if campo is not None:
            logger.sucesso("[Chat] Compositor pronto após criação do chat.")
        else:
            logger.aviso(
                "[Chat] Compositor não detectado após criação — "
                "_executar_geracao tentará localizar com timeout próprio."
            )

        return url_novo

    def _localizar_botao_novo_chat(self):
        """Localiza o botão de novo chat na interface do Adapta.org.

        Tenta múltiplos seletores CSS e XPath para cobrir variações de layout.

        Returns:
            WebElement do botão ou None se não encontrado.
        """
        driver = self.handler.driver

        for sel in SELECTORS_PROJETO["botao_novo_chat"]:
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, sel)
                for e in elems:
                    if e.is_displayed() and e.is_enabled():
                        return e
            except Exception:
                continue

        palavras_chave = ["novo chat", "new chat", "nova conversa", "new conversation",
                          "criar chat", "create chat"]
        for palavra in palavras_chave:
            xpath = (
                f"//button[contains(translate(normalize-space(.), "
                f"'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{palavra}')]"
                f" | //a[contains(translate(normalize-space(.), "
                f"'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{palavra}')]"
            )
            try:
                elems = driver.find_elements(By.XPATH, xpath)
                for e in elems:
                    if e.is_displayed() and e.is_enabled():
                        return e
            except Exception:
                continue

        return None

    def _renomear_chat(self, titulo: str) -> bool:
        """Tenta renomear o chat atual com o título do cliente.

        Busca campos de título editáveis (input ou contenteditable) e
        digita o novo nome. Falha silenciosamente se não encontrar.

        Args:
            titulo: Novo título a aplicar ao chat.

        Returns:
            True se renomeado com sucesso.
        """
        driver = self.handler.driver

        for sel in SELECTORS_PROJETO["titulo_chat"]:
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, sel)
                for elem in elems:
                    if not (elem.is_displayed() and elem.is_enabled()):
                        continue
                    try:
                        elem.click()
                        time.sleep(0.3)
                        elem.send_keys(Keys.CONTROL + "a")
                        time.sleep(0.2)
                        elem.clear()
                        time.sleep(0.2)
                        self._digitar_naturalista(elem, titulo, delay_min=0.02, delay_max=0.05)
                        time.sleep(0.3)
                        elem.send_keys(Keys.RETURN)
                        time.sleep(0.5)
                        logger.info(f"[Chat] Chat renomeado para '{titulo}'.")
                        return True
                    except Exception:
                        continue
            except Exception:
                continue

        logger.aviso(f"[Chat] Não foi possível renomear chat para '{titulo}'.")
        return False

    def _titulo_chat_para_cliente(self, codigo_cliente: str, nome_cliente: str) -> str:
        """Gera o título padronizado do chat para um cliente.

        Formato: '[CODIGO] - [Nome do Cliente]'
        Exemplo: 'DUDE - Dude Clothing'

        Este título é usado tanto para nomear novos chats quanto
        para encontrar chats existentes na lista do sidebar.

        Args:
            codigo_cliente: Código do cliente (ex: DUDE).
            nome_cliente: Nome legível do cliente.

        Returns:
            Título formatado.
        """
        codigo = codigo_cliente.strip().upper()
        nome = nome_cliente.strip()
        if nome and nome.upper() != codigo:
            return f"{codigo} - {nome}"
        return codigo

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

        logger.info(f"Iniciando geração de {solicitacao.protocolo} - {total} artes")
        imagens_geradas: List[Path] = []

        todos_prompts = solicitacao.prompts

        for idx, prompt_bruto in enumerate(prompts_validos, start=1):
            if self._cancelado:
                logger.aviso("Geração cancelada pelo usuário.")
                break

            while self._pausado:
                time.sleep(0.5)
                if self._cancelado:
                    break

            indice_no_total = -1
            for j, p in enumerate(todos_prompts):
                if p and str(p).strip() == prompt_bruto:
                    indice_no_total = j
                    break

            prompt_composto = compor_prompt_arte(
                perfil=perfil,
                tema=solicitacao.tema,
                prompt_principal=prompt_bruto,
                variacoes=todos_prompts,
                indice_prompt_principal=indice_no_total,
                numero_arte=idx,
                total_artes=total,
            )

            logger.info(
                f"Gerando arte {idx}/{total} - Prompt: {truncar_texto(prompt_bruto, 60)}"
            )
            logger.info(
                f"[Composer] Prompt composto ({len(prompt_composto)} chars) "
                f"para arte {idx}/{total}"
            )
            self._emitir_progresso(idx - 1, total)

            nome = nome_arquivo_arte(solicitacao.protocolo, idx)
            arquivo = self._gerar_com_retry(
                prompt=prompt_composto,
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
        self, prompt: str, downloader: DownloadManager, nome_arquivo: str
    ) -> Optional[Path]:
        """Executa o fluxo de geração de uma única arte.

        Usa `_aguardar_compositor` como estratégia unificada de localização
        do campo de entrada — a mesma lógica que funciona para rename, agora
        aplicada ao envio de prompt.

        Fluxo:
            1. Aguarda compositor ficar disponível (timeout 15s).
            2. Faz scroll + foco explícito no campo.
            3. Limpa o campo com método correto para o tipo (textarea vs contenteditable).
            4. Digita o prompt com delay natural.
            5. Clica em Enviar (ou pressiona Enter como fallback).

        Args:
            prompt: Texto do prompt composto.
            downloader: Instância do DownloadManager.
            nome_arquivo: Nome do arquivo de saída.

        Returns:
            Path do arquivo gerado ou None.

        Raises:
            NoSuchElementException: Se o compositor não for encontrado.
        """
        driver = self.handler.driver

        logger.info(
            f"[Composer] Aguardando compositor antes de digitar prompt "
            f"({len(prompt)} chars)..."
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

        # Scroll para garantir visibilidade
        try:
            driver.execute_script(
                "arguments[0].scrollIntoView({block:'center',inline:'center'});",
                campo,
            )
            time.sleep(0.3)
        except Exception:
            pass

        # Clique para garantir foco
        try:
            driver.execute_script("arguments[0].click();", campo)
        except Exception:
            try:
                campo.click()
            except Exception:
                pass
        time.sleep(0.3)

        # Forçar foco via JS (necessário em contenteditable)
        try:
            driver.execute_script("arguments[0].focus();", campo)
            time.sleep(0.2)
        except Exception:
            pass

        # Limpar campo com método adequado ao tipo
        self._limpar_campo_compositor(campo)
        time.sleep(0.3)

        # Digitar prompt com delay natural
        self._digitar_naturalista(campo, prompt)
        time.sleep(0.5)

        # Enviar
        botao = self._localizar_botao_gerar()
        if botao is None:
            logger.info("[Composer] Botão de envio não encontrado — usando Enter.")
            campo.send_keys(Keys.RETURN)
        else:
            logger.info("[Composer] Clicando botão de envio.")
            botao.click()

        logger.info("Aguardando geração da imagem...")
        arquivo = self._aguardar_e_baixar(downloader, nome_arquivo)
        return arquivo

    def _localizar_campo_prompt(self):
        """Localiza o campo de texto de prompt na página.

        Atalho legado — usa `_aguardar_compositor` internamente com timeout curto.
        Mantido para compatibilidade com código externo.

        Returns:
            WebElement do campo ou None.
        """
        return self._aguardar_compositor(timeout_s=5)

    def _aguardar_compositor(self, timeout_s: int = 15) -> Optional[object]:
        """Aguarda e retorna o campo de entrada do compositor do chat.

        Estratégia unificada usada tanto para validação de chat (após
        navegação) quanto para envio de prompt (antes de digitar).

        Polling a cada 2s até timeout_s. Em cada ciclo, coleta todos os
        candidatos editáveis visíveis, pontua cada um por contexto (posição
        na página, ancestrais, proximidade de botão de envio) e retorna
        o melhor.

        Args:
            timeout_s: Tempo máximo de espera em segundos.

        Returns:
            WebElement do compositor ou None se não encontrado.
        """
        deadline = time.time() + timeout_s
        tentativa = 0

        while time.time() < deadline:
            tentativa += 1
            candidatos = self._coletar_candidatos_compositor()

            if candidatos:
                melhor = self._escolher_melhor_compositor(candidatos)
                if melhor is not None:
                    tag = melhor.tag_name
                    ce = melhor.get_attribute("contenteditable") or ""
                    descricao = f"div[contenteditable=true]" if ce == "true" else tag
                    logger.info(
                        f"[Composer] Campo encontrado via '{descricao}' "
                        f"(tentativa {tentativa}, {len(candidatos)} candidato(s) avaliado(s))."
                    )
                    return melhor

            restante = deadline - time.time()
            if tentativa == 1 and restante > 0:
                logger.info(
                    f"[Composer] Campo não encontrado na tentativa {tentativa}. "
                    f"Aguardando estabilização da UI ({restante:.0f}s restantes)..."
                )
            time.sleep(2)

        self._logar_diagnostico_compositor()
        return None

    def _coletar_candidatos_compositor(self) -> list:
        """Coleta todos os campos editáveis visíveis e habilitados da página.

        Busca por: div[contenteditable], textarea, input[type=text].

        Returns:
            Lista de WebElements visíveis e habilitados.
        """
        driver = self.handler.driver
        candidatos = []
        seletores = [
            "div[contenteditable='true']",
            "p[contenteditable='true']",
            "[contenteditable='true']",
            "textarea",
            "input[type='text']",
        ]
        for sel in seletores:
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, sel)
                for elem in elems:
                    try:
                        if elem.is_displayed() and elem.is_enabled():
                            candidatos.append(elem)
                    except Exception:
                        continue
            except Exception:
                continue
        return candidatos

    def _escolher_melhor_compositor(self, candidatos: list) -> Optional[object]:
        """Escolhe o melhor candidato a compositor de chat entre os disponíveis.

        Aplica pontuação baseada em contexto para distinguir o compositor
        principal do chat de outros campos editáveis (ex: título/rename
        no topo da página).

        Critérios de pontuação:
          +30 — ancestral com classe/id relacionado a chat, message, composer
          +20 — botão de envio visível como irmão próximo
          +15 — campo na metade inferior da viewport
          +10 — largura > 200px (campo amplo = compositor principal)
          −50 — ancestral é header/nav/sidebar/title/rename

        Args:
            candidatos: Lista de WebElements candidatos.

        Returns:
            WebElement com maior pontuação, ou None se todos < -10.
        """
        driver = self.handler.driver

        def _pontuar(elem) -> int:
            score = 0
            try:
                anc_pos = (
                    "./ancestor::*["
                    "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'chat') or "
                    "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'message') or "
                    "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'composer') or "
                    "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'input-area') or "
                    "contains(translate(@id,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'chat') or "
                    "contains(translate(@id,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'message')"
                    "]"
                )
                if elem.find_elements(By.XPATH, anc_pos):
                    score += 30

                anc_neg = (
                    "./ancestor::*["
                    "self::header or self::nav or "
                    "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'header') or "
                    "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'sidebar') or "
                    "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'title') or "
                    "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'rename') or "
                    "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'nav')"
                    "]"
                )
                if elem.find_elements(By.XPATH, anc_neg):
                    score -= 50

                botoes = elem.find_elements(
                    By.XPATH,
                    "./following-sibling::button[@type='submit' or contains(@class,'send') or contains(@aria-label,'send') or contains(@aria-label,'enviar')] | "
                    "./parent::*/following-sibling::*//button | "
                    "./parent::*/child::button",
                )
                if any(b.is_displayed() for b in botoes):
                    score += 20

                rect = driver.execute_script(
                    "var r=arguments[0].getBoundingClientRect();"
                    "return {top:r.top,width:r.width};",
                    elem,
                )
                vh = driver.execute_script("return window.innerHeight;")
                if rect and vh:
                    if rect.get("top", 0) > vh * 0.4:
                        score += 15
                    if rect.get("width", 0) > 200:
                        score += 10
            except Exception:
                pass
            return score

        pontuados = []
        for c in candidatos:
            try:
                pontuados.append((_pontuar(c), c))
            except Exception:
                pontuados.append((0, c))

        if not pontuados:
            return None

        pontuados.sort(key=lambda x: x[0], reverse=True)
        melhor_score, melhor = pontuados[0]

        logger.info(
            f"[Composer] {len(candidatos)} candidato(s). "
            f"Melhor: tag='{melhor.tag_name}' score={melhor_score}."
        )

        if melhor_score < -10:
            logger.aviso(
                "[Composer] Todos os candidatos estão em contexto inválido "
                "(header/nav/title). Nenhum compositor válido selecionado."
            )
            return None

        return melhor

    def _limpar_campo_compositor(self, campo) -> None:
        """Limpa o conteúdo do campo de entrada do compositor.

        Trata corretamente tanto textarea/input quanto div[contenteditable].
        Para contenteditable, o método `clear()` do Selenium não funciona —
        é necessário usar JS e/ou combinações de teclas.

        Args:
            campo: WebElement do compositor.
        """
        driver = self.handler.driver
        tag = campo.tag_name.lower()
        ce = campo.get_attribute("contenteditable") or ""

        if ce == "true" or tag not in ("textarea", "input"):
            try:
                driver.execute_script("arguments[0].innerHTML = '';", campo)
                time.sleep(0.1)
            except Exception:
                pass
            try:
                campo.send_keys(Keys.CONTROL + "a")
                time.sleep(0.1)
                campo.send_keys(Keys.DELETE)
                time.sleep(0.1)
            except Exception:
                pass
        else:
            try:
                campo.send_keys(Keys.CONTROL + "a")
                time.sleep(0.2)
                campo.clear()
                time.sleep(0.1)
            except Exception:
                pass

    def _logar_diagnostico_compositor(self) -> None:
        """Emite log diagnóstico detalhado quando o compositor não é encontrado.

        Informa URL atual, título da página, quantidade de candidatos
        encontrados por seletor e se cada um estava visível/habilitado.
        Útil para depuração sem precisar de screenshot.
        """
        driver = self.handler.driver
        try:
            logger.aviso(
                f"[Composer][Diagnóstico] URL atual: {driver.current_url}"
            )
            logger.aviso(
                f"[Composer][Diagnóstico] Título da página: {driver.title}"
            )
        except Exception:
            pass

        seletores_diag = [
            "div[contenteditable='true']",
            "[contenteditable='true']",
            "textarea",
            "input[type='text']",
        ]
        for sel in seletores_diag:
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, sel)
                visiveis = sum(1 for e in elems if e.is_displayed())
                logger.aviso(
                    f"[Composer][Diagnóstico] '{sel}': "
                    f"{len(elems)} elemento(s), {visiveis} visível(is)."
                )
            except Exception:
                logger.aviso(f"[Composer][Diagnóstico] '{sel}': erro ao buscar.")

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
