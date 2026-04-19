"""
Seletores CSS, XPath e dicionários de localização de elementos do Adapta.org.

Centraliza todos os seletores usados pelos módulos de login, navegação e
geração de imagens. Quando o site Adapta.org muda sua estrutura HTML,
apenas este arquivo precisa ser atualizado.
"""

SELECTORS_LOGIN = {
    "email": [
        "input[type='email']",
        "input[name*='email' i]",
        "input[id*='email' i]",
        "input[placeholder*='e-mail' i]",
        "input[placeholder*='email' i]",
        "input[placeholder*='usu\u00e1rio' i]",
        "input[name*='user' i]",
    ],
    "senha": [
        "input[type='password']",
        "input[name*='password' i]",
        "input[name*='senha' i]",
        "input[id*='password' i]",
        "input[id*='senha' i]",
        "input[autocomplete*='password' i]",
        "input[autocomplete*='current-password' i]",
    ],
    "botao_continuar": [
        "button[type='submit']",
        "input[type='submit']",
        "button[class*='continue' i]",
        "button[class*='continuar' i]",
        "button[class*='next' i]",
        "button[class*='login' i]",
        "button[class*='signin' i]",
        "button[class*='entrar' i]",
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
        "input[placeholder*='t\u00edtulo' i]", "input[placeholder*='title' i]",
        "input[placeholder*='nome' i]", "textarea[class*='title' i]",
        "[contenteditable='true']",
    ],
}
