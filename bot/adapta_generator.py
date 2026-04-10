"""
Lógica de geração de artes no Adapta.org via Selenium.
"""

from __future__ import annotations

import time
import random
from pathlib import Path
from typing import Callable, List, Optional, Tuple, TYPE_CHECKING

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementNotInteractableException,
    StaleElementReferenceException,
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
        # --- Padrões de botão de envio de chat (aria-label) ---
        "button[aria-label*='send' i]",
        "button[aria-label*='enviar' i]",
        "button[aria-label*='submit' i]",
        "button[aria-label*='mensagem' i]",
        "button[aria-label*='message' i]",
        # --- data-testid ---
        "button[data-testid*='send']",
        "button[data-testid*='submit']",
        "button[data-testid*='enviar']",
        # --- Por classe ---
        "button[class*='send' i]",
        "button[class*='submit' i]",
        "button[type='submit']",
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
        # --- Por aria-label (mais confiável em SPAs acessíveis) ---
        "//button[contains(translate(@aria-label,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'send')]",
        "//button[contains(translate(@aria-label,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'enviar')]",
        "//button[contains(translate(@aria-label,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'submit')]",
        # --- Adjacente ao contenteditable (posicional) ---
        "//div[@contenteditable='true']/following-sibling::button[1]",
        "//div[@contenteditable='true']/parent::*/following-sibling::button[1]",
        "//div[@contenteditable='true']/parent::*/button[last()]",
        "//div[@contenteditable='true']/ancestor::form//button[@type='submit']",
        # --- Por texto do botão ---
        "//button[contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'enviar')]",
        "//button[contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'send')]",
        "//button[contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'gerar')]",
        "//button[contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'generate')]",
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
            resultado = self.tentar_login_automatico(email, senha)
            if resultado == "ok":
                logger.sucesso("Login automático realizado com sucesso.")
                self._navegar_para_adapta_one()
                return True
            if resultado == "campos_nao_encontrados":
                logger.aviso(
                    "Login automático falhou: campos do formulário não localizados "
                    "na página. A interface pode não ter carregado completamente — "
                    "verifique o seletor ou tente login manual."
                )
            else:
                logger.aviso(
                    "Login automático falhou: credenciais inválidas ou redirecionamento "
                    "inesperado. Verifique e-mail/senha em Configurações ou faça login manual."
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

    def tentar_login_automatico(self, email: str, senha: str) -> str:
        """Preenche e submete o formulário de login do Adapta.org.

        Aguarda os campos do formulário por até 10 s (React SPA renderiza async).
        Diferencia claramente os cenários de falha.

        Args:
            email: E-mail de login.
            senha: Senha de login.

        Returns:
            'ok'                   se login bem-sucedido.
            'campos_nao_encontrados' se o formulário não foi localizado na página.
            'credenciais_invalidas'  se preencheu mas a tela de login voltou.
            'erro'                   se ocorreu exceção inesperada.
        """
        driver = self.handler.driver

        # Aguardar campos do formulário (SPA pode renderizar async)
        logger.info("[Login] Aguardando campos do formulário (até 10s)...")
        campo_email = None
        campo_senha = None
        deadline_campos = time.time() + 10

        while time.time() < deadline_campos:
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

            if campo_email and campo_senha:
                logger.info(
                    f"[Login] Campos localizados — e-mail: {campo_email.get_attribute('name') or 'n/a'}, "
                    f"senha: {campo_senha.get_attribute('name') or 'n/a'}."
                )
                break

            time.sleep(1)

        if not campo_email or not campo_senha:
            encontrados = []
            if campo_email:
                encontrados.append("e-mail")
            if campo_senha:
                encontrados.append("senha")
            faltando = [f for f in ["e-mail", "senha"] if f not in encontrados]
            logger.aviso(
                f"[Login] Campos não localizados após 10s: faltando {faltando}. "
                f"A interface de login pode não ter carregado ou seus seletores mudaram."
            )
            return "campos_nao_encontrados"

        try:
            logger.info("[Login] Preenchendo e-mail...")
            campo_email.clear()
            self._digitar_naturalista(campo_email, email)
            time.sleep(0.3)

            logger.info("[Login] Preenchendo senha...")
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
                logger.info("[Login] Clicando botão de login...")
                botao.click()
            else:
                logger.info("[Login] Botão não encontrado — submetendo via Enter.")
                campo_senha.send_keys(Keys.RETURN)

            time.sleep(4)

            if self._detectar_tela_login():
                logger.aviso("[Login] Tela de login ainda ativa após submissão.")
                return "credenciais_invalidas"

            return "ok"

        except Exception as exc:
            logger.aviso(f"[Login] Erro durante login automático: {exc}")
            return "erro"

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
            "[Chat] Rename concluído. Aguardando input de rename desaparecer..."
        )
        self._aguardar_fim_rename(timeout_s=8)

        logger.info(
            "[Chat] Aguardando compositor ficar pronto para envio de prompt..."
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

    def _inserir_prompt_compositor(self, campo, texto: str) -> bool:
        """Insere o texto completo no compositor de forma atômica.

        Para div[contenteditable]: usa ``document.execCommand('insertText')``
        que insere o texto inteiro — incluindo quebras de linha — SEM disparar
        teclas Enter e portanto SEM fragmentar em múltiplas mensagens.

        Estratégia em cascata:
            1. ``execCommand('insertText')`` — sem efeito colateral de Enter.
            2. Manipulação direta do DOM + InputEvent — para SPAs que ignoram execCommand.
            3. ``send_keys`` com ``Shift+Enter`` para preservar \\n — somente como último recurso.

        Args:
            campo: WebElement do compositor (contenteditable, textarea ou input).
            texto: Texto completo a inserir.

        Returns:
            True se inserção foi validada, False se falhou completamente.
        """
        driver = self.handler.driver
        tag = campo.tag_name.lower()
        ce = campo.get_attribute("contenteditable") or ""
        metodo = "desconhecido"

        if ce == "true" or tag not in ("textarea", "input"):
            # --- Tentativa 1: execCommand (React/Vue disparam eventos sintéticos) ---
            try:
                resultado = driver.execute_script(
                    """
                    var el = arguments[0];
                    var txt = arguments[1];
                    el.focus();
                    document.execCommand('selectAll', false, null);
                    document.execCommand('delete', false, null);
                    return document.execCommand('insertText', false, txt);
                    """,
                    campo, texto,
                )
                if resultado:
                    metodo = "execCommand(insertText)"
                else:
                    raise RuntimeError("execCommand retornou false")
            except Exception as e1:
                logger.aviso(
                    f"[Composer] execCommand falhou ({e1}) "
                    f"— tentando DOM+InputEvent"
                )
                # --- Tentativa 2: DOM direto + InputEvent ---
                try:
                    driver.execute_script(
                        """
                        var el = arguments[0];
                        var txt = arguments[1];
                        el.innerHTML = '';
                        el.focus();
                        var tn = document.createTextNode(txt);
                        el.appendChild(tn);
                        el.dispatchEvent(new InputEvent('input', {
                            inputType: 'insertText',
                            data: txt,
                            bubbles: true,
                            cancelable: false
                        }));
                        el.dispatchEvent(new Event('change', {bubbles: true}));
                        """,
                        campo, texto,
                    )
                    metodo = "DOM+InputEvent"
                except Exception as e2:
                    logger.aviso(
                        f"[Composer] DOM+InputEvent falhou ({e2}) "
                        f"— usando send_keys com Shift+Enter para multiline"
                    )
                    # --- Tentativa 3: send_keys com Shift+Enter (sem fragmentar) ---
                    try:
                        self._limpar_campo_compositor(campo)
                        linhas = texto.split("\n")
                        for i, linha in enumerate(linhas):
                            if i > 0:
                                campo.send_keys(Keys.SHIFT + Keys.RETURN)
                            campo.send_keys(linha)
                        metodo = "send_keys+Shift+Enter"
                    except Exception as e3:
                        logger.erro(
                            f"[Composer] Todas as tentativas de inserção falharam: {e3}"
                        )
                        return False
        else:
            # textarea / input: setter nativo React + disparar eventos
            try:
                driver.execute_script(
                    """
                    var el = arguments[0];
                    var v = arguments[1];
                    var tag = el.tagName.toLowerCase();
                    var proto = tag === 'textarea'
                        ? window.HTMLTextAreaElement.prototype
                        : window.HTMLInputElement.prototype;
                    var setter = Object.getOwnPropertyDescriptor(proto, 'value');
                    if (setter && setter.set) {
                        setter.set.call(el, v);
                    } else {
                        el.value = v;
                    }
                    el.dispatchEvent(new Event('input', {bubbles: true}));
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                    """,
                    campo, texto,
                )
                metodo = "JS-nativeSetter"
            except Exception as exc:
                logger.aviso(f"[Composer] JS setter falhou ({exc}) — send_keys")
                try:
                    campo.send_keys(Keys.CONTROL + "a")
                    campo.clear()
                    campo.send_keys(texto)
                    metodo = "send_keys"
                except Exception as exc2:
                    logger.erro(f"[Composer] send_keys falhou: {exc2}")
                    return False

        # Validação pós-inserção
        try:
            if ce == "true" or tag not in ("textarea", "input"):
                conteudo = driver.execute_script(
                    "return (arguments[0].innerText "
                    "|| arguments[0].textContent || '').trim();",
                    campo,
                ) or ""
            else:
                conteudo = (campo.get_attribute("value") or "").strip()

            c_esp = len(texto.strip())
            c_obt = len(conteudo)
            logger.info(
                f"[Composer] Inserção '{metodo}': "
                f"{c_obt}/{c_esp} chars no campo."
            )
            return c_obt >= int(c_esp * 0.85)
        except Exception:
            logger.info(f"[Composer] Inserção '{metodo}': validação indisponível — assumindo OK.")
            return True

    def _contar_mensagens_usuario(self) -> int:
        """Conta os elementos de mensagem do usuário visíveis no DOM do chat.

        Tenta vários seletores comuns em SPAs de chat. Retorna o maior
        valor encontrado entre os seletores — evita subcontagem.

        Returns:
            Número inteiro de mensagens do usuário (0 se nenhuma/erro).
        """
        driver = self.handler.driver
        seletores = [
            "[data-role='user']",
            "[data-message-role='user']",
            "[data-author-role='user']",
            ".user-message",
            ".human-message",
            "[class*='user-message' i]",
            "[class*='human-message' i]",
            "[class*='user-bubble' i]",
            "[class*='outgoing' i]",
        ]
        maximo = 0
        for sel in seletores:
            try:
                n = len(driver.find_elements(By.CSS_SELECTOR, sel))
                if n > maximo:
                    maximo = n
            except Exception:
                continue
        return maximo

    def _confirmar_envio_real(
        self,
        campo,
        texto_inserido: str,
        timeout_s: float = 5.0,
        arte_label: str = "Arte",
    ) -> bool:
        """Confirma que o prompt foi realmente enviado ao chat.

        Verifica três sinais independentes, em polling até ``timeout_s``:

        - **Sinal A (primário)**: campo do compositor está vazio/limpo.
          Em quase todos os SPAs de chat, o campo é zerado imediatamente
          após o envio bem-sucedido.
        - **Sinal B (secundário)**: indicador de loading/geração apareceu,
          o que implica que a resposta foi acionada.
        - **Sinal C (terciário)**: a contagem de mensagens do usuário no
          DOM aumentou — nova mensagem ficou visível no histórico.

        Retorna ``True`` assim que qualquer sinal for confirmado, sem
        esperar os outros. Retorna ``False`` apenas se o timeout expirar
        sem nenhum sinal positivo E o texto ainda estiver no campo.

        Args:
            campo: WebElement do compositor.
            texto_inserido: Texto enviado (para log de diagnóstico).
            timeout_s: Tempo máximo de espera em segundos.
            arte_label: Rótulo para log (ex: 'Arte 2/3').

        Returns:
            True se envio confirmado, False caso contrário.
        """
        driver = self.handler.driver
        n_msgs_antes = self._contar_mensagens_usuario()
        inicio = time.time()

        while time.time() - inicio < timeout_s:
            # ── Sinal A: campo vazio ──
            try:
                conteudo = driver.execute_script(
                    "var e = arguments[0];"
                    "return (e.innerText || e.textContent || e.value || '').trim();",
                    campo,
                ) or ""
                if len(conteudo) < 5:
                    logger.info(
                        f"[Envio] {arte_label}: ✓ campo vazio após envio "
                        f"(sinal A — primário)."
                    )
                    return True
            except StaleElementReferenceException:
                # Elemento recriado pelo SPA após envio — confirma que enviou
                logger.info(
                    f"[Envio] {arte_label}: ✓ campo substituído pelo SPA "
                    f"(StaleElement — sinal A implícito)."
                )
                return True
            except Exception:
                pass

            # ── Sinal B: loading/geração iniciou ──
            for sel in SELECTORS["indicador_carregando"]:
                try:
                    elems = driver.find_elements(By.CSS_SELECTOR, sel)
                    if any(e.is_displayed() for e in elems):
                        logger.info(
                            f"[Envio] {arte_label}: ✓ loading detectado "
                            f"(sinal B — secundário)."
                        )
                        return True
                except Exception:
                    continue

            # ── Sinal C: nova mensagem do usuário no DOM ──
            n_msgs_agora = self._contar_mensagens_usuario()
            if n_msgs_agora > n_msgs_antes:
                logger.info(
                    f"[Envio] {arte_label}: ✓ nova mensagem do usuário detectada "
                    f"({n_msgs_antes} → {n_msgs_agora}) (sinal C — terciário)."
                )
                return True

            time.sleep(0.4)

        # ── Avaliação final ──
        try:
            conteudo_final = driver.execute_script(
                "var e = arguments[0];"
                "return (e.innerText || e.textContent || e.value || '').trim();",
                campo,
            ) or ""
        except StaleElementReferenceException:
            logger.info(
                f"[Envio] {arte_label}: ✓ campo destruído após timeout "
                f"(StaleElement — confirmação final)."
            )
            return True
        except Exception:
            conteudo_final = ""

        texto_no_campo = len(conteudo_final) > 5
        logger.aviso(
            f"[Envio] {arte_label}: texto ainda no campo após {timeout_s:.0f}s? "
            f"{'SIM' if texto_no_campo else 'não'} "
            f"({len(conteudo_final)} chars). "
            f"Envio {'NÃO confirmado' if texto_no_campo else 'provavelmente OK (campo vazio)'}."
        )
        return not texto_no_campo

    def _enviar_via_enter_confirmado(
        self,
        campo,
        texto_inserido: str,
        arte_label: str,
        max_tentativas: int = 3,
    ) -> bool:
        """Tenta enviar via Enter com validação de foco e confirmação real.

        Para cada tentativa:
        1. Verifica se o campo ainda é o ``activeElement``.
        2. Se não, refoca via click + JS focus.
        3. Verifica se o texto ainda está no campo (pode já ter sido enviado).
        4. Envia ``Keys.RETURN``.
        5. Chama ``_confirmar_envio_real`` — só retorna True com prova.

        Args:
            campo: WebElement do compositor.
            texto_inserido: Texto a verificar no campo.
            arte_label: Rótulo para log.
            max_tentativas: Número máximo de tentativas de Enter.

        Returns:
            True se envio confirmado em alguma tentativa, False caso contrário.
        """
        driver = self.handler.driver

        for tentativa in range(1, max_tentativas + 1):
            # ── Verificar se campo ainda é o elemento ativo ──
            try:
                eh_ativo = driver.execute_script(
                    "return document.activeElement === arguments[0];", campo
                )
            except StaleElementReferenceException:
                logger.info(
                    f"[Envio] {arte_label}: campo substituído pelo SPA antes do Enter "
                    f"(tentativa {tentativa}) — assumindo envio OK."
                )
                return True
            except Exception:
                eh_ativo = False

            logger.info(
                f"[Envio] {arte_label}: composer focado? "
                f"{'sim' if eh_ativo else 'não'} "
                f"(tentativa Enter {tentativa}/{max_tentativas})."
            )

            if not eh_ativo:
                logger.info(
                    f"[Envio] {arte_label}: recuperando foco antes do Enter..."
                )
                try:
                    driver.execute_script(
                        "arguments[0].scrollIntoView({block:'center'});"
                        "arguments[0].click();"
                        "arguments[0].focus();",
                        campo,
                    )
                    time.sleep(0.3)
                    eh_ativo = driver.execute_script(
                        "return document.activeElement === arguments[0];", campo
                    )
                    logger.info(
                        f"[Envio] {arte_label}: foco recuperado? "
                        f"{'sim' if eh_ativo else 'NÃO'}."
                    )
                except StaleElementReferenceException:
                    logger.info(
                        f"[Envio] {arte_label}: StaleElement ao refocusar — "
                        f"SPA recriou o campo, assumindo envio já ocorreu."
                    )
                    return True
                except Exception as exc:
                    logger.aviso(
                        f"[Envio] {arte_label}: falha ao recuperar foco: {exc}"
                    )

            # ── Verificar se texto ainda está no campo ──
            try:
                conteudo = driver.execute_script(
                    "var e = arguments[0];"
                    "return (e.innerText || e.textContent || e.value || '').trim();",
                    campo,
                ) or ""
                texto_no_campo = len(conteudo) > 5
            except StaleElementReferenceException:
                logger.info(
                    f"[Envio] {arte_label}: StaleElement ao verificar conteúdo — "
                    f"campo destruído, envio provavelmente ocorreu."
                )
                return True
            except Exception:
                texto_no_campo = True
                conteudo = ""

            logger.info(
                f"[Envio] {arte_label}: texto no campo? "
                f"{'sim' if texto_no_campo else 'não'} "
                f"({len(conteudo)} chars)."
            )

            if not texto_no_campo:
                logger.info(
                    f"[Envio] {arte_label}: campo já vazio antes do Enter "
                    f"— envio ocorreu em tentativa anterior."
                )
                return True

            # ── Enviar Enter ──
            logger.info(
                f"[Envio] {arte_label}: enviando Enter "
                f"(tentativa {tentativa}/{max_tentativas})..."
            )
            try:
                campo.send_keys(Keys.RETURN)
            except StaleElementReferenceException:
                logger.info(
                    f"[Envio] {arte_label}: StaleElement no send_keys — "
                    f"campo recriado após Enter, provável envio bem-sucedido."
                )
                return True
            except Exception as exc:
                logger.aviso(
                    f"[Envio] {arte_label}: send_keys(Enter) falhou ({exc}) "
                    f"— tentando KeyboardEvent via JS."
                )
                try:
                    driver.execute_script(
                        "arguments[0].dispatchEvent(new KeyboardEvent('keydown',{"
                        "key:'Enter',code:'Enter',keyCode:13,which:13,"
                        "bubbles:true,cancelable:true}));",
                        campo,
                    )
                except Exception:
                    pass

            logger.info(
                f"[Envio] {arte_label}: Enter enviado. Aguardando confirmação..."
            )
            confirmado = self._confirmar_envio_real(
                campo, texto_inserido, timeout_s=5.0, arte_label=arte_label
            )
            if confirmado:
                return True

            logger.aviso(
                f"[Envio] {arte_label}: tentativa {tentativa}/{max_tentativas} "
                f"de Enter não confirmou envio."
            )
            if tentativa < max_tentativas:
                time.sleep(1.0)

        logger.erro(
            f"[Envio] {arte_label}: todas as {max_tentativas} tentativas de Enter "
            f"falharam. Prompt pode estar parado no composer."
        )
        return False

    def _enviar_prompt_compositor(self, campo, texto_inserido: str = "", arte_label: str = "Arte") -> Tuple[str, bool]:
        """Envia o prompt digitado no compositor. Retorna (método, confirmado).

        Fluxo:
        1. Busca botão de envio (3s) → clica → ``_confirmar_envio_real``.
        2. Se botão não encontrado ou confirmação falhou:
           → ``_enviar_via_enter_confirmado`` (valida foco, Enter, confirma).
        3. Retorna ``(método_usado, envio_confirmado)``.

        Nunca retorna ``True`` sem prova concreta de envio.

        Args:
            campo: WebElement do compositor (para fallback Enter).
            texto_inserido: Texto que foi inserido (para confirmação).
            arte_label: Rótulo para log (ex: 'Arte 2/3').

        Returns:
            Tupla ``(str, bool)`` — método e se envio foi confirmado.
        """
        driver = self.handler.driver
        t_ini = time.time()

        # ── Tentativa 1: Botão de envio ──
        logger.info(f"[Envio] {arte_label}: tentativa de envio via botão iniciada.")
        botao = None
        deadline = time.time() + 3.0
        while time.time() < deadline:
            botao = self._localizar_botao_gerar()
            if botao:
                break
            time.sleep(0.5)

        t_busca = time.time() - t_ini

        if botao:
            logger.info(
                f"[Envio] {arte_label}: botão encontrado em {t_busca:.1f}s. Clicando..."
            )
            try:
                driver.execute_script("arguments[0].click();", botao)
            except Exception:
                try:
                    botao.click()
                except Exception as exc_click:
                    logger.aviso(
                        f"[Envio] {arte_label}: clique no botão falhou: {exc_click}"
                    )

            logger.info(
                f"[Envio] {arte_label}: botão clicado. Aguardando confirmação de envio..."
            )
            confirmado = self._confirmar_envio_real(
                campo, texto_inserido, timeout_s=5.0, arte_label=arte_label
            )
            if confirmado:
                logger.info(f"[Envio] {arte_label}: envio confirmado via botão.")
                return "botao", True

            logger.aviso(
                f"[Envio] {arte_label}: botão clicado mas envio NÃO confirmado "
                f"— caindo para fallback Enter."
            )
        else:
            logger.info(
                f"[Envio] {arte_label}: botão não encontrado após {t_busca:.1f}s "
                f"— usando Enter como fallback."
            )

        # ── Tentativa 2: Enter com validação de foco e confirmação ──
        logger.info(f"[Envio] {arte_label}: tentativa de envio via Enter iniciada.")
        confirmado = self._enviar_via_enter_confirmado(
            campo, texto_inserido, arte_label, max_tentativas=3
        )
        return "enter", confirmado

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

        Estratégia em 3 rodadas progressivamente mais permissivas:

        - **padrao** (0% a 40% do timeout): heurística padrão, threshold=0.
          Penaliza levemente header/sidebar/rename. Não penaliza 'title'
          quando já estamos em URL de chat ativo.
        - **relaxado** (40% a 75% do timeout): penalidades mínimas (só
          header/sidebar reais). Threshold=-5.
        - **fallback** (>75% do timeout): sem penalidades. Retorna qualquer
          candidato visível. Se ainda assim scoring falhar, testa
          funcionalmente cada contenteditable com click+focus.

        Args:
            timeout_s: Tempo máximo de espera total em segundos.

        Returns:
            WebElement do compositor ou None se não encontrado.
        """
        inicio = time.time()
        deadline = inicio + timeout_s
        tentativa = 0

        while time.time() < deadline:
            tentativa += 1
            decorrido = time.time() - inicio
            restante = deadline - time.time()

            if timeout_s >= 8:
                if decorrido < timeout_s * 0.40:
                    modo = "padrao"
                elif decorrido < timeout_s * 0.75:
                    modo = "relaxado"
                else:
                    modo = "fallback"
            else:
                modo = "padrao" if decorrido < timeout_s * 0.6 else "fallback"

            candidatos = self._coletar_candidatos_compositor()

            if not candidatos:
                logger.info(
                    f"[Composer] Tentativa {tentativa} ({modo}): "
                    f"0 candidatos visíveis — aguardando... ({restante:.0f}s)"
                )
                time.sleep(2)
                continue

            melhor = self._escolher_melhor_compositor(candidatos, modo=modo)

            if melhor is not None:
                tag = melhor.tag_name
                ce = melhor.get_attribute("contenteditable") or ""
                tipo = f"{tag}[contenteditable=true]" if ce == "true" else tag
                logger.info(
                    f"[Composer] Compositor resolvido: tipo='{tipo}', "
                    f"modo='{modo}', tentativa={tentativa}."
                )
                return melhor

            if restante > 2:
                logger.info(
                    f"[Composer] Tentativa {tentativa} ({modo}): "
                    f"nenhum candidato aprovado. {restante:.0f}s restantes."
                )
            time.sleep(2)

        self._logar_diagnostico_compositor()

        # Último recurso: teste funcional direto em cada contenteditable visível
        logger.aviso(
            "[Composer] Timeout atingido. Tentando teste funcional direto "
            "em candidatos contenteditable..."
        )
        try:
            driver = self.handler.driver
            ces = driver.find_elements(By.CSS_SELECTOR, "[contenteditable='true']")
            for ce_elem in ces:
                try:
                    if ce_elem.is_displayed() and ce_elem.is_enabled():
                        if self._verificar_foco_funcional(ce_elem):
                            logger.sucesso(
                                "[Composer] Compositor encontrado via teste funcional direto."
                            )
                            return ce_elem
                except Exception:
                    continue
        except Exception:
            pass

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

    def _escolher_melhor_compositor(
        self, candidatos: list, modo: str = "padrao"
    ) -> Optional[object]:
        """Escolhe o melhor candidato a compositor de chat entre os disponíveis.

        Usa pontuação por contexto com três modos progressivamente mais
        permissivos. Penalidades são sempre **sinais fracos**, nunca vetos
        absolutos. O URL atual é o sinal mais forte de que estamos em um
        chat ativo e qualquer contenteditable visível provavelmente é o
        compositor correto.

        Pontuação:
          +20  URL atual é de chat válido (sinal primário)
          +25  ancestral contém chat/message/composer/editor/input
          +15  botão de envio visível próximo
          +12  campo na metade inferior da viewport
          + 5  campo no terço central da viewport
          +10  largura > 300px | +5 largura > 150px
          + 5  altura > 30px
          + 5  tag contenteditable | +3 tag textarea
          − 8  ancestral é header/sidebar (modo=padrao)
          − 5  ancestral contém 'title'/'nav' (apenas se não em chat ativo)
          − 4  ancestral é header/sidebar (modo=relaxado)
          modo=fallback: sem penalidades, aceita qualquer candidato visível

        Args:
            candidatos: Lista de WebElements visíveis e habilitados.
            modo: 'padrao' | 'relaxado' | 'fallback'

        Returns:
            WebElement escolhido, ou None se melhor_score < threshold.
        """
        driver = self.handler.driver

        try:
            url_atual = driver.current_url
            em_chat_ativo = self._e_url_de_chat_valida(url_atual)
        except Exception:
            em_chat_ativo = False

        def _pontuar_detalhado(elem) -> tuple:
            score = 0
            detalhes = {}
            try:
                tag = elem.tag_name.lower()
                ce = elem.get_attribute("contenteditable") or ""

                if ce == "true":
                    score += 5
                    detalhes["ce"] = "+5"
                elif tag == "textarea":
                    score += 3
                    detalhes["textarea"] = "+3"

                if em_chat_ativo:
                    score += 20
                    detalhes["url_chat"] = "+20"

                anc_pos = (
                    "./ancestor::*["
                    "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'chat') or "
                    "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'message') or "
                    "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'composer') or "
                    "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'editor') or "
                    "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'input') or "
                    "contains(translate(@id,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'chat') or "
                    "contains(translate(@id,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'message') or "
                    "contains(translate(@id,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'composer')"
                    "]"
                )
                if elem.find_elements(By.XPATH, anc_pos):
                    score += 25
                    detalhes["anc_pos"] = "+25"

                if modo == "padrao":
                    anc_neg_strict = (
                        "./ancestor::*["
                        "self::header or self::nav or "
                        "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'sidebar') or "
                        "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'rename')"
                        "]"
                    )
                    if elem.find_elements(By.XPATH, anc_neg_strict):
                        score -= 8
                        detalhes["anc_neg_strict"] = "-8"

                    if not em_chat_ativo:
                        anc_neg_title = (
                            "./ancestor::*["
                            "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'title') or "
                            "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'nav')"
                            "]"
                        )
                        if elem.find_elements(By.XPATH, anc_neg_title):
                            score -= 5
                            detalhes["anc_neg_title"] = "-5"

                elif modo == "relaxado":
                    anc_neg_min = (
                        "./ancestor::*["
                        "self::header or "
                        "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'sidebar')"
                        "]"
                    )
                    if elem.find_elements(By.XPATH, anc_neg_min):
                        score -= 4
                        detalhes["anc_neg_min"] = "-4"

                botoes = elem.find_elements(
                    By.XPATH,
                    "./following-sibling::button | "
                    "./preceding-sibling::button | "
                    "./parent::*/following-sibling::*//button | "
                    "./parent::*/child::button",
                )
                if any(b.is_displayed() for b in botoes):
                    score += 15
                    detalhes["botao_proximo"] = "+15"

                rect = driver.execute_script(
                    "var r=arguments[0].getBoundingClientRect();"
                    "return {top:r.top,width:r.width,height:r.height};",
                    elem,
                )
                vh = driver.execute_script("return window.innerHeight;")
                if rect and vh:
                    topo = rect.get("top", 0)
                    larg = rect.get("width", 0)
                    alt = rect.get("height", 0)
                    if topo > vh * 0.5:
                        score += 12
                        detalhes["pos_inferior"] = f"+12(top={topo:.0f})"
                    elif topo > vh * 0.3:
                        score += 5
                        detalhes["pos_centro"] = f"+5(top={topo:.0f})"
                    if larg > 300:
                        score += 10
                        detalhes["campo_largo"] = f"+10(w={larg:.0f})"
                    elif larg > 150:
                        score += 5
                        detalhes["campo_medio"] = f"+5(w={larg:.0f})"
                    if alt > 30:
                        score += 5
                        detalhes["campo_alto"] = f"+5(h={alt:.0f})"
            except Exception as exc:
                detalhes["exc"] = str(exc)[:60]
            return score, detalhes

        pontuados = []
        for c in candidatos:
            try:
                s, d = _pontuar_detalhado(c)
                pontuados.append((s, d, c))
            except Exception:
                pontuados.append((0, {}, c))

        if not pontuados:
            return None

        pontuados.sort(key=lambda x: x[0], reverse=True)

        for i, (s, d, c) in enumerate(pontuados):
            tag = c.tag_name
            ce = c.get_attribute("contenteditable") or ""
            tipo = f"{tag}[ce=true]" if ce == "true" else tag
            det_str = ", ".join(f"{k}:{v}" for k, v in d.items()) or "sem_bonus"
            logger.info(
                f"[Composer] [{modo}] Cand {i+1}/{len(pontuados)}: "
                f"tipo={tipo}, score={s} | {det_str}"
            )

        melhor_score, _, melhor = pontuados[0]

        if modo == "fallback":
            logger.info(
                f"[Composer] Fallback: aceitando melhor candidato "
                f"disponível (score={melhor_score})."
            )
            return melhor

        threshold = 0 if modo == "padrao" else -5
        if melhor_score >= threshold:
            return melhor

        logger.aviso(
            f"[Composer] [{modo}] Melhor score={melhor_score} < threshold={threshold}. "
            f"Aguardando próxima rodada..."
        )
        return None

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

    def _verificar_foco_funcional(self, campo) -> bool:
        """Testa se um elemento aceita foco real via click + JS focus.

        Usado como teste final antes de descartar um candidato a compositor.
        Verifica se `document.activeElement` corresponde ao elemento após
        o foco, confirmando que ele está interativo e não apenas decorativo.

        Args:
            campo: WebElement candidato.

        Returns:
            True se o elemento ficou ativo após foco.
        """
        driver = self.handler.driver
        try:
            driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", campo
            )
            time.sleep(0.2)
            driver.execute_script("arguments[0].click();", campo)
            time.sleep(0.2)
            driver.execute_script("arguments[0].focus();", campo)
            time.sleep(0.2)
            eh_ativo = driver.execute_script(
                "return document.activeElement === arguments[0];", campo
            )
            if eh_ativo:
                logger.info(
                    f"[Composer] Teste funcional OK: "
                    f"tag='{campo.tag_name}' ficou ativo após focus."
                )
                return True
            logger.aviso(
                f"[Composer] Teste funcional FALHOU: "
                f"tag='{campo.tag_name}' não ficou ativo após focus "
                f"(activeElement é outro)."
            )
            return False
        except Exception as exc:
            logger.aviso(f"[Composer] Teste funcional ERRO: {exc}")
            return False

    def _aguardar_fim_rename(self, timeout_s: int = 8) -> None:
        """Aguarda o input temporário de rename desaparecer após criação de chat.

        Após pressionar Enter no campo de título, o Adapta One pode demorar
        um momento para remover o input temporário e exibir o compositor
        principal. Esta função aguarda até o input[autofocus] sumir ou até
        o timeout.

        Args:
            timeout_s: Tempo máximo de espera em segundos.
        """
        driver = self.handler.driver
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            try:
                autofocus = driver.find_elements(
                    By.CSS_SELECTOR, "input[autofocus]"
                )
                visiveis = [e for e in autofocus if e.is_displayed()]
                if not visiveis:
                    logger.info(
                        "[Chat] Input de rename não mais visível — "
                        "UI estabilizada para envio de prompt."
                    )
                    return
            except Exception:
                pass
            time.sleep(0.5)
        logger.aviso(
            "[Chat] Input de rename ainda presente após timeout de "
            f"{timeout_s}s — continuando mesmo assim."
        )

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
        self,
        downloader: DownloadManager,
        nome_arquivo: str,
        snapshot_antes: Optional[set] = None,
        urls_baixadas: Optional[set] = None,
        numero_arte: int = 0,
        total_artes: int = 0,
    ) -> Optional[Path]:
        """Aguarda a imagem gerada e baixa APENAS a imagem nova desta arte.

        Compara o estado do DOM contra o snapshot tirado antes do envio.
        Só considera imagens cujas URLs não estejam em ``snapshot_antes``
        nem em ``urls_baixadas`` — eliminando duplicatas entre artes.

        Args:
            downloader: Instância do DownloadManager.
            nome_arquivo: Nome do arquivo de saída.
            snapshot_antes: URLs de imagens presentes antes do envio.
            urls_baixadas: Conjunto compartilhado de URLs já baixadas no ciclo.
            numero_arte: Número desta arte (para log).
            total_artes: Total de artes (para log).

        Returns:
            Path do arquivo ou None.
        """
        driver = self.handler.driver
        inicio = time.time()
        _snapshot = snapshot_antes if snapshot_antes is not None else set()
        _baixadas = urls_baixadas if urls_baixadas is not None else set()
        arte_label = f"Arte {numero_arte}/{total_artes}" if numero_arte else "Arte"

        # Conjunto de todas as URLs já conhecidas = não baixar novamente
        vistas: set = _snapshot | _baixadas

        # Rastreamento de estado para diferenciar os 4 casos de falha (C6):
        # estado 2 = "envio OK, resposta demorou" → nunca viu nova imagem
        # estado 3 = "resposta chegou, imagem não detectada" → detectou mas URL inválida
        # estado 4 = "imagem detectada, download falhou"
        alguma_nova_detectada = False
        algum_download_tentado = False

        logger.info(
            f"[Download] {arte_label}: snapshot antes={len(_snapshot)}, "
            f"já baixadas={len(_baixadas)}. Aguardando imagem nova..."
        )

        while time.time() - inicio < self.timeout:
            if self._cancelado:
                return None

            self._aguardar_fim_loading(driver, espera_max=5)

            # ── Coletar imagens novas (HTTP URLs) ──
            novas = self._coletar_novas_imagens(vistas)

            snap_atual = len(vistas)
            logger.info(
                f"[Download] {arte_label}: snapshot após envio={snap_atual + len(novas)} imgs "
                f"({len(novas)} nova(s) detectada(s))."
            )

            for url_nova in novas:
                alguma_nova_detectada = True
                id_log = url_nova[:80] + ("..." if len(url_nova) > 80 else "")
                if url_nova in _baixadas:
                    logger.info(
                        f"[Download] {arte_label}: imagem ignorada por já ter sido "
                        f"processada — {id_log}"
                    )
                    vistas.add(url_nova)
                    continue

                logger.info(
                    f"[Download] {arte_label}: imagem selecionada para download — {id_log}"
                )
                algum_download_tentado = True
                arquivo = downloader.baixar_de_url(url_nova, nome_arquivo)
                if arquivo and downloader.verificar_arquivo(arquivo):
                    _baixadas.add(url_nova)
                    logger.sucesso(
                        f"[Download] {arte_label}: download concluído. "
                        f"URL registrada para deduplicação."
                    )
                    return arquivo

                logger.aviso(
                    f"[Download] {arte_label}: falha ao baixar {id_log}. Tentando próxima."
                )
                vistas.add(url_nova)

            # ── Fallback: data URIs e canvas ──
            arquivo = self._tentar_baixar_via_js_novo(downloader, nome_arquivo, vistas)
            if arquivo and downloader.verificar_arquivo(arquivo):
                logger.sucesso(
                    f"[Download] {arte_label}: download concluído via fallback JS."
                )
                return arquivo

            time.sleep(2)

        # ── Diagnóstico preciso do estado de falha (C6) ──
        if not alguma_nova_detectada:
            msg_estado = (
                f"[Download] {arte_label}: ESTADO 2 — envio confirmado, "
                f"mas nenhuma imagem nova apareceu em {self.timeout}s. "
                f"A resposta do Adapta pode ter demorado além do timeout, "
                f"ou a imagem usa formato/seletor não detectado."
            )
        elif algum_download_tentado:
            msg_estado = (
                f"[Download] {arte_label}: ESTADO 4 — imagem(ns) detectada(s) "
                f"mas todos os downloads falharam (URL inacessível ou arquivo inválido)."
            )
        else:
            msg_estado = (
                f"[Download] {arte_label}: ESTADO 3 — resposta chegou, "
                f"imagem foi detectada mas filtros de dedup/URL a rejeitaram. "
                f"Verifique se a URL da imagem é nova ou se foi deduplicada incorretamente."
            )

        raise TimeoutException(msg_estado)

    def _tirar_snapshot_imagens(self) -> set:
        """Captura as URLs HTTP de todas as imagens visíveis no momento.

        Usado para estabelecer o baseline antes de enviar o prompt.
        Qualquer URL ausente neste snapshot após o envio é candidata
        à imagem gerada pela arte atual.

        Returns:
            Conjunto de strings de URL (``http://...``).
        """
        driver = self.handler.driver
        try:
            resultado = driver.execute_script(
                """
                var urls = [];
                document.querySelectorAll('img').forEach(function(img) {
                    if (img.naturalWidth > 100 && img.naturalHeight > 100
                            && img.src && img.src.indexOf('http') === 0
                            && img.offsetWidth > 0) {
                        urls.push(img.src);
                    }
                });
                return urls;
                """
            ) or []
            return set(resultado)
        except Exception:
            return set()

    def _coletar_novas_imagens(self, vistas: set) -> list:
        """Retorna URLs HTTP de imagens visíveis não presentes em ``vistas``.

        Varre todo o DOM por ``<img>`` com naturalWidth > 100 e src HTTP.
        Exclui qualquer URL já presente em ``vistas`` (snapshot + baixadas).

        Args:
            vistas: Conjunto de URLs já conhecidas (não devem ser baixadas).

        Returns:
            Lista ordenada (DOM order) de URLs novas.
        """
        driver = self.handler.driver
        try:
            todas = driver.execute_script(
                """
                var urls = [];
                document.querySelectorAll('img').forEach(function(img) {
                    if (img.naturalWidth > 100 && img.naturalHeight > 100
                            && img.src && img.src.indexOf('http') === 0
                            && img.offsetWidth > 0) {
                        urls.push(img.src);
                    }
                });
                return urls;
                """
            ) or []
            return [u for u in todas if u not in vistas]
        except Exception:
            return []

    def _tentar_baixar_via_js_novo(
        self,
        downloader: DownloadManager,
        nome_arquivo: str,
        urls_excluidas: set,
    ) -> Optional[Path]:
        """Fallback JS para canvas e data URIs ignorados pela varredura HTTP.

        Percorre canvas e img[src^='data:image'] em ordem reversa (mais novo
        primeiro) e baixa o primeiro que não esteja em ``urls_excluidas``.

        Args:
            downloader: Instância do DownloadManager.
            nome_arquivo: Nome do arquivo de saída.
            urls_excluidas: URLs que já foram processadas — não baixar novamente.

        Returns:
            Path do arquivo salvo ou None.
        """
        driver = self.handler.driver
        try:
            script = """
            var excluidas = arguments[0];
            // Canvas (mais recente primeiro)
            var canvases = document.querySelectorAll('canvas');
            for (var i = canvases.length - 1; i >= 0; i--) {
                if (canvases[i].offsetWidth < 100) continue;
                try {
                    var dataUrl = canvases[i].toDataURL('image/jpeg', 0.95);
                    if (excluidas.indexOf(dataUrl.substring(0, 100)) === -1) {
                        return dataUrl;
                    }
                } catch(e) {}
            }
            // Imagens data: URI
            var imgs = document.querySelectorAll('img[src^="data:image"]');
            for (var j = imgs.length - 1; j >= 0; j--) {
                if (imgs[j].naturalWidth > 200 && imgs[j].naturalHeight > 200) {
                    var src = imgs[j].src;
                    if (excluidas.indexOf(src.substring(0, 100)) === -1) {
                        return src;
                    }
                }
            }
            return null;
            """
            excluidas_prefixos = [u[:100] for u in urls_excluidas]
            resultado = driver.execute_script(script, excluidas_prefixos)
            if resultado and resultado.startswith("data:image"):
                return downloader._salvar_base64(
                    resultado, downloader.pasta_output / nome_arquivo
                )
        except Exception:
            pass
        return None

    def _aguardar_estabilizacao_spa(
        self, arte_label: str = "Arte", timeout_s: int = 8
    ) -> None:
        """Aguarda a SPA estabilizar entre artes (C9).

        Após o download de uma arte, o Adapta One pode re-renderizar a UI:
        criar novo estado de chat, recriar o compositor, atualizar o
        histórico. Enviar a próxima arte enquanto isso ocorre causa perda de
        foco, botão de envio não encontrado e Enter sem efeito.

        Verifica:
        1. Indicadores de loading desapareceram.
        2. URL não mudou nos últimos 1s (navegação SPA se estabilizou).
        3. Breve pausa fixa para permitir reconciliação do React/DOM.

        Args:
            arte_label: Rótulo para log.
            timeout_s: Tempo máximo de espera.
        """
        driver = self.handler.driver
        logger.info(
            f"[SPA] {arte_label}: aguardando estabilização da UI antes da próxima arte..."
        )

        inicio = time.time()

        # 1. Aguardar loading desaparecer
        self._aguardar_fim_loading(driver, espera_max=min(timeout_s, 5))

        # 2. Aguardar URL estabilizar (SPA pode navegar brevemente)
        url_anterior = ""
        estavel_desde = None
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            try:
                url_atual = driver.current_url
            except Exception:
                break
            if url_atual == url_anterior:
                if estavel_desde is None:
                    estavel_desde = time.time()
                elif time.time() - estavel_desde >= 1.0:
                    logger.info(
                        f"[SPA] {arte_label}: URL estável por 1s ({url_atual[:60]}...)."
                    )
                    break
            else:
                estavel_desde = None
                if url_anterior:
                    logger.info(
                        f"[SPA] {arte_label}: URL mudou após arte anterior "
                        f"({url_anterior[:40]} → {url_atual[:40]})."
                    )
                url_anterior = url_atual
            time.sleep(0.3)

        # 3. Pausa fixa mínima para reconciliação do DOM
        time.sleep(0.5)
        logger.info(
            f"[SPA] {arte_label}: estabilização concluída em "
            f"{time.time() - inicio:.1f}s."
        )

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
