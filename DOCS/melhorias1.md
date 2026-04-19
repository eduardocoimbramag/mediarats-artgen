# Documento de Melhorias — Media Rats Artgen
**Versão do Documento:** 1.0  
**Data:** Abril de 2026  
**Base de Análise:** Código-fonte v1.0.0  
**Escopo:** Análise técnica completa de todos os módulos do projeto

---

## Sumário

1. [Melhorias de Funcionamento](#1-melhorias-de-funcionamento)
2. [Melhorias de Desempenho](#2-melhorias-de-desempenho)
3. [Melhorias de Arquitetura](#3-melhorias-de-arquitetura)
4. [Melhorias de Manutenção e Organização](#4-melhorias-de-manutenção-e-organização)
5. [Melhorias de Interface](#5-melhorias-de-interface)
6. [Melhorias de Automação](#6-melhorias-de-automação)
7. [Melhorias de Segurança e Robustez](#7-melhorias-de-segurança-e-robustez)
8. [Melhorias de Experiência do Usuário](#8-melhorias-de-experiência-do-usuário)
9. [Melhorias de Escalabilidade](#9-melhorias-de-escalabilidade)
10. [Melhorias Futuras / Roadmap](#10-melhorias-futuras--roadmap)
11. [Priorização Recomendada por Etapas](#11-priorização-recomendada-por-etapas)

---

## 1. Melhorias de Funcionamento

### 1.1 Processamento sequencial — ausência de fila automática

**Problema atual:**  
O sistema processa apenas uma solicitação por vez e exige interação manual do usuário para iniciar cada geração. Não há mecanismo de fila automática que percorra todas as solicitações com status "Planejado" ou "Pendente" em sequência.

**Por que melhorar:**  
O caso de uso principal da ferramenta é gerar artes em lote para múltiplos clientes. Ter que clicar em "Iniciar Geração" para cada protocolo individualmente aumenta drasticamente o tempo operacional e exige atenção contínua do operador.

**Como implementar:**  
Criar um botão "Processar Fila Completa" no painel de controles. Implementar um mecanismo no `GeracaoWorker` (ou criar um `FilaWorker`) que itere sobre as solicitações pendentes em sequência, respeitando pausas e cancelamentos.

```python
# Exemplo de estrutura
class FilaAutoWorker(QThread):
    def run(self):
        for sol in self._solicitacoes_pendentes:
            if self._cancelado:
                break
            worker = GeracaoWorker(sol, self._handler)
            worker.run()  # executa em série dentro da mesma thread
```

**Impacto esperado:** Redução de 80–90% no tempo de supervisão humana para lotes grandes.  
**Dependências técnicas:** `GeracaoWorker`, `FilaPanel`, `ControlesPanel`.  
**Prioridade:** **Alta**

---

### 1.2 Processamento de planilha com múltiplas aberturas por operação

**Problema atual:**  
Em operações compostas — como carregar e gerar — a planilha Excel é aberta e fechada diversas vezes desnecessariamente. Por exemplo, `_carregar_planilha` em `main_window.py` chama `ExcelReader._abrir()` e logo após `ExcelWriter.criar_estrutura_planilha()`, que também abre o arquivo. Depois, ao gerar, `GeracaoWorker._carregar_perfil_cliente` abre o arquivo mais uma vez. Em uma única operação simples, o arquivo pode ser aberto 3 ou 4 vezes.

**Por que melhorar:**  
Cada abertura de arquivo com `openpyxl.load_workbook` consome tempo de I/O e pode causar condições de corrida em sistemas mais lentos ou em redes.

**Como implementar:**  
Extrair um método `_abrir_e_executar(fn)` no `ExcelWriter` que abre uma vez, executa a função fornecida e fecha. Para operações combinadas, implementar um contexto de transação:

```python
class ExcelTransaction:
    def __init__(self, caminho):
        self._wb = openpyxl.load_workbook(caminho)
    def __enter__(self):
        return self._wb
    def __exit__(self, *_):
        self._wb.save(self._caminho)
        self._wb.close()
```

**Impacto esperado:** Redução do número de I/Os em planilha; eliminação de race conditions.  
**Dependências técnicas:** `excel/reader.py`, `excel/writer.py`.  
**Prioridade:** **Média**

---

### 1.3 Geração não respeita `data_planejada` automaticamente

**Problema atual:**  
A coluna `DATA_PLANEJADA` é lida da planilha e exibida na fila, mas o sistema não filtra nem prioriza solicitações com base nessa data. Solicitações para datas futuras aparecem misturadas às de hoje.

**Por que melhorar:**  
O campo existe para planejamento editorial. Sem essa lógica, o operador precisa verificar manualmente quais solicitações devem ser geradas hoje.

**Como implementar:**  
Adicionar um checkbox "Mostrar apenas de hoje/atrasadas" no painel de fila. Implementar filtro em `FilaPanel.carregar_solicitacoes`:

```python
hoje = date.today()
pendentes_hoje = [
    s for s in solicitacoes
    if s.data_planejada is None or s.data_planejada <= hoje
]
```

**Impacto esperado:** Operação alinhada com o calendário editorial; menos erros humanos.  
**Dependências técnicas:** `excel/reader.py` (`Solicitacao.data_planejada`), `gui/fila_panel.py`.  
**Prioridade:** **Média**

---

### 1.4 Ausência de validação de prompt antes do envio

**Problema atual:**  
O sistema envia prompts diretamente ao Adapta.org sem validação prévia de conteúdo. Prompts vazios ou extremamente curtos passam pela `prompt_composer.py` e chegam ao bot, resultando apenas em um log de erro tardio.

**Por que melhorar:**  
Detectar o problema antes de abrir o navegador evita desperdício de tempo e recursos.

**Como implementar:**  
Adicionar validação em `_iniciar_geracao` na `MainWindow`:

```python
prompts_validos = sol.prompts_validos()
if not prompts_validos:
    QMessageBox.warning(self, "Sem Prompts", 
        f"O protocolo {sol.protocolo} não possui prompts preenchidos.")
    return
if any(len(p.strip()) < 10 for p in prompts_validos):
    # aviso de prompt muito curto
```

**Impacto esperado:** Feedback imediato ao usuário; eliminação de gerações abortadas.  
**Dependências técnicas:** `excel/reader.py`, `gui/main_window.py`.  
**Prioridade:** **Alta**

---

### 1.5 `verificar_internet` não fecha o socket corretamente

**Problema atual:**  
Em `utils/helpers.py`, a função `verificar_internet` cria um socket mas não o fecha no bloco `finally`, criando um vazamento de recurso leve:

```python
socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, porta))
# socket nunca fechado explicitamente
```

**Como implementar:**  
Refatorar para usar `with` ou `finally`:

```python
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s.settimeout(timeout)
    s.connect((host, porta))
    return True
except socket.error:
    return False
finally:
    s.close()
```

**Impacto esperado:** Eliminação de vazamento de descritores de arquivo em uso prolongado.  
**Prioridade:** **Média**

---

## 2. Melhorias de Desempenho

### 2.1 `openpyxl` sem modo `read_only` nas operações de leitura

**Problema atual:**  
`ExcelReader._abrir()` usa `openpyxl.load_workbook(self.caminho, data_only=True)` sem `read_only=True`. O modo `read_only` é significativamente mais rápido para planilhas grandes, pois carrega apenas os dados sem construir a estrutura completa de células em memória.

**Por que melhorar:**  
Em planilhas com centenas de linhas e muitas colunas (especialmente após acumulação de avaliações na aba `AVALIACAO_DETALHADA`), a diferença de tempo de carregamento pode ser de 3x a 10x.

**Como implementar:**  
```python
# ExcelReader._abrir()
wb = openpyxl.load_workbook(
    self.caminho, 
    data_only=True, 
    read_only=True  # adicionar aqui
)
```

> **Atenção:** `read_only=True` é incompatível com `write`. O `ExcelWriter` **não** deve usar esse flag.

**Impacto esperado:** Leitura de planilha 3–10x mais rápida conforme ela cresce.  
**Dependências técnicas:** `excel/reader.py`.  
**Prioridade:** **Alta**

---

### 2.2 Ausência de cache de leitura da planilha

**Problema atual:**  
Toda vez que uma operação ocorre (iniciar geração, abrir diálogo de clientes, recarregar), a planilha é relida do disco. Como o arquivo não muda entre essas leituras na maioria dos fluxos normais, esse trabalho é redundante.

**Por que melhorar:**  
Tempo de resposta da UI melhorado. Menos travamentos perceptíveis ao usuário.

**Como implementar:**  
Implementar um cache simples com timestamp de invalidação em `MainWindow`:

```python
self._cache_planilha: Optional[Tuple[float, List[Solicitacao]]] = None
CACHE_TTL = 5.0  # segundos

def _obter_solicitacoes_cached(self) -> List[Solicitacao]:
    agora = time.monotonic()
    if self._cache_planilha and agora - self._cache_planilha[0] < self.CACHE_TTL:
        return self._cache_planilha[1]
    reader = ExcelReader(Config.caminho_planilha_abs())
    sols = reader.ler_solicitacoes(apenas_pendentes=False)
    self._cache_planilha = (agora, sols)
    return sols
```

Invalidar o cache após `atualizar_status`, `adicionar_solicitacao` e `remover_solicitacao`.

**Impacto esperado:** Carregamento da interface mais responsivo.  
**Dependências técnicas:** `gui/main_window.py`, `excel/reader.py`.  
**Prioridade:** **Média**

---

### 2.3 `time.sleep()` bloqueante em esperas do Selenium

**Problema atual:**  
`adapta_generator.py` e `selenium_handler.py` utilizam `time.sleep()` com valores fixos (ex.: `time.sleep(3)` em `acessar_adapta`). Essas esperas bloqueiam a thread completamente e não são interrompíveis por cancelamento.

**Por que melhorar:**  
O sistema precisa de até 3 segundos apenas para checar se o login é necessário. Em fluxos longos com 10 artes, esses sleeps se acumulam significativamente. Além disso, ao cancelar a geração, a thread pode ficar presa em um sleep não interrompível.

**Como implementar:**  
Substituir `time.sleep(n)` por uma espera interrompível:

```python
def _aguardar(self, segundos: float) -> None:
    """Aguarda por intervalos de 0.1s, respeitando cancelamento."""
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        if self._cancelado:
            return
        time.sleep(0.1)
```

**Impacto esperado:** Cancelamento imediato; redução de até 15–20s por geração em casos ideais.  
**Dependências técnicas:** `bot/adapta_generator.py`, `bot/selenium_handler.py`.  
**Prioridade:** **Alta**

---

### 2.4 `ExcelWriter` abre o workbook separadamente em cada método

**Problema atual:**  
Ao concluir uma geração, `_on_geracao_concluida` chama sequencialmente `writer.atualizar_status(sol, "Gerado")` e depois `writer.registrar_avaliacao(sol, caminhos_rel)`. Cada chamada abre, escreve e fecha o arquivo Excel independentemente — resultando em dois ciclos completos de I/O para uma única operação lógica.

**Como implementar:**  
Criar um método combinado `registrar_conclusao`:

```python
def registrar_conclusao(self, solicitacao, caminhos_imagens):
    wb = openpyxl.load_workbook(self.caminho)
    # atualiza status
    self._atualizar_status_wb(wb, solicitacao, "Gerado")
    # registra avaliação
    self._registrar_avaliacao_wb(wb, solicitacao, caminhos_imagens)
    wb.save(self.caminho)
    wb.close()
```

**Impacto esperado:** 50% de redução nas operações de I/O de escrita após cada geração.  
**Prioridade:** **Média**

---

## 3. Melhorias de Arquitetura

### 3.1 `adapta_generator.py` com 2774 linhas — God Object

**Problema atual:**  
O arquivo `bot/adapta_generator.py` contém 2774 linhas e mistura responsabilidades completamente distintas: gestão de login, navegação de UI, envio de prompts, detecção de imagem, download, lógica de retry, mapeamento de projetos e seletores CSS. É o maior problema arquitetural do projeto.

**Por que melhorar:**  
Arquivos monolíticos são difíceis de testar, modificar e entender. Um bug no login exige navegar por centenas de linhas não relacionadas. Qualquer mudança no site Adapta.org força edição nesse arquivo gigante.

**Como implementar:**  
Dividir em módulos menores e coesos:

```
bot/
├── adapta_generator.py     # orquestrador principal (mantém gerar_solicitacao)
├── login_handler.py        # lógica de login automático
├── chat_handler.py         # interação com o chat (envio de prompt, espera)
├── image_detector.py       # detecção e extração de imagens
├── project_navigator.py    # navegação de pastas/projetos no Adapta
├── selectors.py            # dicionários SELECTORS, XPATHS, SELECTORS_LOGIN
└── download_manager.py     # já existente, manter
```

**Impacto esperado:** Redução drástica de complexidade por módulo; manutenção e testes isolados.  
**Dependências técnicas:** Refatoração interna sem quebrar contratos externos.  
**Prioridade:** **Alta**

---

### 3.2 `Config` como classe com atributos de classe

**Problema atual:**  
`utils/config.py` usa `Config` como uma classe cujos atributos de classe são lidos no momento de importação via `os.getenv`. O método `recarregar()` precisa reatribuir manualmente cada atributo. Esse padrão é frágil, dificulta testes unitários (impossível instanciar com configurações diferentes) e pode ter comportamento inesperado em imports.

**Por que melhorar:**  
Testes automatizados precisam criar configurações isoladas. O padrão atual impossibilita isso sem monkey-patching.

**Como implementar:**  
Converter para uma instância singleton ou dataclass:

```python
from dataclasses import dataclass, field
from functools import lru_cache

@dataclass
class Config:
    url_adapta: str = field(default_factory=lambda: os.getenv("URL_ADAPTA", "..."))
    caminho_planilha: str = field(default_factory=lambda: os.getenv("CAMINHO_PLANILHA", "..."))
    # ...

@lru_cache(maxsize=1)
def get_config() -> Config:
    return Config()
```

Em testes: `get_config.cache_clear()` antes de cada teste que modifica envs.

**Impacto esperado:** Testabilidade; clareza de quando as configurações são carregadas.  
**Dependências técnicas:** Todos os módulos que importam `Config`.  
**Prioridade:** **Média**

---

### 3.3 `GeracaoWorker` definido dentro de `main_window.py`

**Problema atual:**  
As classes `WorkerSignals` e `GeracaoWorker` estão definidas no mesmo arquivo que `MainWindow` (`gui/main_window.py`, 717 linhas). Isso acopla a lógica de geração diretamente à camada de UI.

**Por que melhorar:**  
O worker deveria ser testável independentemente da UI. Separação clara de responsabilidades (UI vs. lógica de domínio).

**Como implementar:**  
Mover para `bot/geracao_worker.py` ou `core/geracao_worker.py`:

```
core/
└── geracao_worker.py   # GeracaoWorker + WorkerSignals
```

`main_window.py` importa: `from core.geracao_worker import GeracaoWorker`.

**Impacto esperado:** `main_window.py` reduzido; worker testável de forma isolada.  
**Prioridade:** **Média**

---

### 3.4 Ausência de camada de serviço (Service Layer)

**Problema atual:**  
`MainWindow` acessa diretamente `ExcelReader`, `ExcelWriter`, `Config` e `SeleniumHandler`. Não há uma camada intermediária de serviço que encapsule as operações de negócio.

**Por que melhorar:**  
A lógica de "carregar solicitações pendentes", "registrar conclusão" e "iniciar geração" é negócio, não UI. Misturar as duas camadas torna a `MainWindow` um controlador god que é impossível de testar.

**Como implementar:**  

```
core/
├── planilha_service.py   # carregar_solicitacoes, registrar_conclusao, etc.
└── geracao_service.py    # orquestra SeleniumHandler + AdaptaGenerator
```

**Impacto esperado:** `MainWindow` vira um controlador fino que apenas reage a eventos e atualiza a UI.  
**Prioridade:** **Média**

---

### 3.5 Comunicação via callback lambda frágil no logger

**Problema atual:**  
Em `main_window.py`:
```python
logger.definir_callback(
    lambda msg, tipo: self._log_panel.adicionar_mensagem(msg, tipo)
)
```
O `ArtgenLogger` aceita apenas um único callback. Se outro módulo chamar `definir_callback`, o callback da `MainWindow` é sobrescrito silenciosamente. Além disso, esse padrão não garante que o callback seja chamado na thread da UI.

**Como implementar:**  
Usar o sistema de sinais do PyQt6. Converter `ArtgenLogger` para `QObject` com sinais:

```python
class ArtgenLogger(QObject):
    mensagem_emitida = pyqtSignal(str, str)
    
    def _emitir(self, mensagem, tipo):
        # ...
        self.mensagem_emitida.emit(linha, tipo)
```

Conectar na `MainWindow`: `logger.mensagem_emitida.connect(self._log_panel.adicionar_mensagem)`

**Impacto esperado:** Thread-safety garantida; múltiplos ouvintes possíveis; desacoplamento.  
**Dependências técnicas:** `utils/logger.py`, `gui/main_window.py`, PyQt6.  
**Prioridade:** **Alta**

---

## 4. Melhorias de Manutenção e Organização

### 4.1 `STATUS_CORES` duplicado em dois módulos

**Problema atual:**  
O dicionário de cores por status existe em duas formas diferentes:
- `excel/writer.py`: `STATUS_CORES = {"Planejado": "FFF9C4", ...}` (cores HEX para Excel)
- `gui/fila_panel.py`: `STATUS_CORES = {"planejado": ("#1e1800", "#ccaa00"), ...}` (cores para PyQt)

Além de serem formatos distintos (o que é justificável), o nome idêntico cria confusão mental. Se um status for adicionado, precisa ser atualizado em dois lugares.

**Como implementar:**  
Criar `utils/status.py` com uma única fonte de verdade:

```python
# utils/status.py
STATUS_VALIDOS = {"Planejado", "Pendente", "Gerando", "Gerado", "Erro", "Cancelado"}

STATUS_CORES_EXCEL = {
    "Planejado": "FFF9C4",
    # ...
}

STATUS_CORES_GUI = {
    "planejado": ("#1e1800", "#ccaa00"),
    # ...
}
```

**Impacto esperado:** Single source of truth; adição de novo status em um único lugar.  
**Prioridade:** **Média**

---

### 4.2 Seletores CSS/XPath hardcoded em `adapta_generator.py`

**Problema atual:**  
Os dicionários `SELECTORS`, `XPATHS`, `SELECTORS_LOGIN` e `SELECTORS_PROJETO` estão definidos como variáveis globais no topo de `adapta_generator.py`. Quando o site Adapta.org muda sua estrutura HTML (o que acontece frequentemente em SPAs), é necessário editar o código Python diretamente.

**Por que melhorar:**  
Separa configuração de código. Permite ao usuário avançado atualizar seletores sem recompilar ou entender Python.

**Como implementar:**  
Externalizar para `bot/selectors.json` ou `bot/selectors.py` dedicado:

```json
{
  "campo_prompt": [
    "div[contenteditable='true']",
    "textarea[placeholder*='prompt' i]"
  ],
  "botao_gerar": [...]
}
```

Carregar no início de `AdaptaGenerator.__init__` com fallback para os valores hardcoded.

**Impacto esperado:** Manutenção de seletores sem alterar lógica Python; possibilidade de atualização sem deploy.  
**Prioridade:** **Média**

---

### 4.3 Ausência total de testes automatizados

**Problema atual:**  
O projeto não possui nenhum arquivo de teste (`test_*.py`, `pytest.ini`, etc.). Refatorações e atualizações são feitas sem rede de segurança.

**Por que melhorar:**  
A maioria das funções utilitárias e de leitura/escrita da planilha é perfeitamente testável sem UI ou Selenium.

**Como implementar:**  
Criar estrutura de testes com `pytest`:

```
tests/
├── conftest.py
├── test_helpers.py          # validar_protocolo, gerar_protocolo, etc.
├── test_excel_reader.py     # leitura com planilhas fixtures
├── test_excel_writer.py     # escrita com planilhas temporárias
├── test_prompt_composer.py  # composição de prompts
└── test_config.py           # carregamento de configurações
```

Exemplo de teste simples:

```python
# test_helpers.py
from utils.helpers import validar_protocolo, gerar_protocolo

def test_protocolo_valido():
    assert validar_protocolo("DUDE#1") is True
    assert validar_protocolo("MR#99") is True

def test_protocolo_invalido():
    assert validar_protocolo("D#1") is False
    assert validar_protocolo("DUDE1") is False
```

**Impacto esperado:** Confiança em refatorações; detecção precoce de regressões.  
**Dependências técnicas:** `pytest`, `pytest-qt` para testes de UI.  
**Prioridade:** **Alta**

---

### 4.4 Logs sem rotação de arquivo

**Problema atual:**  
`utils/logger.py` cria um `FileHandler` simples para `logs/artgen.log`. Em uso contínuo, esse arquivo cresce indefinidamente, podendo atingir centenas de MB ao longo de meses de operação.

**Como implementar:**  
Usar `RotatingFileHandler` do Python:

```python
from logging.handlers import RotatingFileHandler

fh = RotatingFileHandler(
    LOG_FILE,
    maxBytes=5 * 1024 * 1024,  # 5 MB por arquivo
    backupCount=5,              # manter até 5 arquivos antigos
    encoding="utf-8",
)
```

**Impacto esperado:** Controle do tamanho dos logs; manutenção automática.  
**Prioridade:** **Média**

---

### 4.5 Sem padronização de type hints em `adapta_generator.py`

**Problema atual:**  
O arquivo `adapta_generator.py` mistura funções com e sem type hints. Métodos como `_detectar_tela_login`, `_aguardar_desaparecimento_loading` e `_tentar_obter_imagem` retornam tipos não anotados ou usam `Optional` de forma inconsistente.

**Como implementar:**  
Adicionar anotações completas a todos os métodos privados. Usar `from __future__ import annotations` (já presente) para adiar avaliação. Considerar executar `mypy` no CI para verificação estática.

**Impacto esperado:** IDE com autocompletion mais preciso; bugs de tipo detectados estaticamente.  
**Prioridade:** **Baixa**

---

## 5. Melhorias de Interface

### 5.1 Estilos CSS inline duplicados em vários arquivos GUI

**Problema atual:**  
Strings de estilo como `"background-color: #0d0d0d; color: #d0d0d0;"`, `"border: 1px solid #1a3a1a;"` e variações do verde `#00ff00` / `#00cc00` aparecem repetidas em `main_window.py`, `fila_panel.py`, `dashboard.py`, `configuracoes_dialog.py` e `clientes_dialog.py`. Qualquer ajuste de cor exige edições em múltiplos arquivos.

**Como implementar:**  
Criar `gui/theme.py` com constantes e funções de estilo:

```python
# gui/theme.py
VERDE_PRIMARIO = "#00ff00"
VERDE_MEDIO = "#00cc00"
FUNDO_PRINCIPAL = "#000000"
FUNDO_CARD = "#0d0d0d"
BORDA = "#1a3a1a"

def estilo_card():
    return f"background-color: {FUNDO_CARD}; border: 1px solid {BORDA}; border-radius: 8px;"

def estilo_input():
    return f"background-color: #111111; color: #d0d0d0; border: 1px solid #282828; border-radius: 4px; padding: 5px 8px;"
```

**Impacto esperado:** Mudança de tema em um único arquivo; consistência visual garantida.  
**Prioridade:** **Média**

---

### 5.2 Sem filtragem e ordenação na tabela da fila

**Problema atual:**  
A `FilaPanel` exibe todas as solicitações em uma tabela `QTableWidget` sem capacidade de busca por texto, filtro por status ou ordenação por coluna. Com muitos protocolos, localizar um item específico exige scroll manual.

**Como implementar:**  
1. Adicionar `QLineEdit` de busca rápida acima da tabela com filtro em tempo real.
2. Habilitar ordenação por clique no cabeçalho: `self._tabela.setSortingEnabled(True)`.
3. Adicionar `QComboBox` de filtro por status.

```python
# Filtro em tempo real
self._busca.textChanged.connect(self._filtrar_tabela)

def _filtrar_tabela(self, texto: str) -> None:
    for row in range(self._tabela.rowCount()):
        visivel = any(
            texto.lower() in (self._tabela.item(row, col).text() or "").lower()
            for col in range(self._tabela.columnCount())
        )
        self._tabela.setRowHidden(row, not visivel)
```

**Impacto esperado:** Navegação muito mais rápida em filas grandes.  
**Prioridade:** **Alta**

---

### 5.3 Sem atalhos de teclado

**Problema atual:**  
Nenhuma ação da interface possui atalho de teclado. Iniciar geração, cancelar, recarregar planilha e abrir configurações exigem sempre o mouse.

**Como implementar:**  
Registrar `QShortcut` na `MainWindow`:

```python
from PyQt6.QtGui import QShortcut, QKeySequence

QShortcut(QKeySequence("F5"), self, activated=self._carregar_planilha)
QShortcut(QKeySequence("Ctrl+Return"), self, activated=self._iniciar_geracao)
QShortcut(QKeySequence("Escape"), self, activated=self._cancelar_geracao)
QShortcut(QKeySequence("Ctrl+,"), self, activated=self._abrir_configuracoes)
```

**Impacto esperado:** Ganho de produtividade para usuários avançados.  
**Prioridade:** **Baixa**

---

### 5.4 Painel de log sem limite de linhas configurável

**Problema atual:**  
`log_panel.py` usa um `QTextEdit` para exibir logs. Em sessões longas, o widget acumula centenas de linhas sem limitação, consumindo memória crescente e tornando o scroll lento.

**Como implementar:**  
Manter um buffer máximo de linhas (ex: 500) e limpar automaticamente as mais antigas:

```python
MAX_LINHAS_LOG = 500

def adicionar_mensagem(self, msg, tipo):
    # adiciona a mensagem
    self._text.append(linha_formatada)
    # limpa excesso
    doc = self._text.document()
    while doc.blockCount() > MAX_LINHAS_LOG:
        cursor = QTextCursor(doc.begin())
        cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
        cursor.removeSelectedText()
        cursor.deleteChar()
```

**Impacto esperado:** Uso de memória estável em sessões longas.  
**Prioridade:** **Média**

---

### 5.5 Sem preview de imagens geradas na UI

**Problema atual:**  
Após a geração, o usuário recebe apenas uma mensagem com o caminho das imagens. Para visualizá-las, precisa abrir o explorador de arquivos manualmente.

**Como implementar:**  
Adicionar um painel ou diálogo de preview usando `QLabel` + `QPixmap`:

```python
class PreviewDialog(QDialog):
    def __init__(self, caminhos: List[str], parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        for caminho in caminhos[:5]:  # exibir até 5
            lbl = QLabel()
            px = QPixmap(caminho).scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio)
            lbl.setPixmap(px)
            layout.addWidget(lbl)
```

**Impacto esperado:** Feedback visual imediato; aprovação/rejeição sem sair da aplicação.  
**Prioridade:** **Média**

---

## 6. Melhorias de Automação

### 6.1 Ausência de modo "Processar Fila Completa"

**Problema atual:**  
Conforme descrito em 1.1, cada solicitação exige interação manual. Não há possibilidade de iniciar o programa e deixá-lo processar todos os protocolos pendentes automaticamente.

**Como implementar:**  
Adicionar opção no menu ou nos controles:

```python
# ControlesPanel
btn_fila = QPushButton("▶▶ Processar Fila")
btn_fila.clicked.connect(self.sinal_processar_fila)
```

O `FilaAutoWorker` processa as solicitações em série, emitindo sinais de progresso após cada conclusão. Entre solicitações, aguarda um intervalo configurável para não sobrecarregar o Adapta.org.

**Impacto esperado:** Operação completamente não assistida para lotes noturnos.  
**Prioridade:** **Alta**

---

### 6.2 Ausência de retry automático por arte

**Problema atual:**  
Quando a geração de uma arte falha (timeout, elemento não encontrado, erro de download), o sistema registra o erro e para. Não há retentativa automática para aquela arte específica antes de marcar como erro.

**Por que melhorar:**  
Falhas transitórias (lentidão do servidor Adapta, timeout de rede) são frequentes em automação web. Uma retentativa automática resolveria a maioria desses casos sem intervenção humana.

**Como implementar:**  
Implementar retry com backoff exponencial no loop de geração em `adapta_generator.py`:

```python
MAX_RETRY_ARTE = 2

for tentativa in range(MAX_RETRY_ARTE + 1):
    imagem = self._gerar_arte_unica(prompt, ...)
    if imagem:
        break
    if tentativa < MAX_RETRY_ARTE:
        logger.aviso(f"Arte {numero} falhou, tentativa {tentativa+1}/{MAX_RETRY_ARTE}...")
        time.sleep(backoff_espera(tentativa))
```

**Impacto esperado:** Redução drástica de intervenções manuais por falhas transitórias.  
**Prioridade:** **Alta**

---

### 6.3 Sem agendamento baseado em `data_planejada`

**Problema atual:**  
O campo `DATA_PLANEJADA` existe, mas o sistema não oferece nenhum mecanismo de agendamento para processar automaticamente as solicitações na data prevista.

**Como implementar:**  
Implementar um verificador de agenda em background usando `QTimer`:

```python
self._timer_agenda = QTimer(self)
self._timer_agenda.timeout.connect(self._verificar_agenda)
self._timer_agenda.start(60_000)  # verificar a cada 1 minuto

def _verificar_agenda(self):
    hoje = date.today()
    for sol in self._solicitacoes:
        if sol.data_planejada == hoje and sol.status.lower() in {"planejado"}:
            logger.info(f"Agenda: {sol.protocolo} agendado para hoje.")
            # opcional: auto-iniciar ou apenas destacar na fila
```

**Impacto esperado:** Operação alinhada com calendário editorial sem supervisão.  
**Prioridade:** **Baixa**

---

### 6.4 Login automático sem suporte a autenticação de dois fatores

**Problema atual:**  
O sistema tenta login automático via preenchimento de formulário. Se a conta Adapta.org tiver 2FA ativo, o processo falha silenciosamente e cai no fluxo de login manual.

**Como implementar:**  
Detectar explicitamente a presença de campos de 2FA na página após o primeiro login:

```python
SELECTORS["campo_2fa"] = [
    "input[name*='code' i]",
    "input[placeholder*='código' i]",
    "input[autocomplete='one-time-code']",
]
```

Ao detectar, emitir sinal `login_necessario` com mensagem específica: *"Autenticação em dois fatores detectada — insira o código manualmente."*

**Impacto esperado:** Feedback claro ao usuário em vez de falha genérica.  
**Prioridade:** **Baixa**

---

## 7. Melhorias de Segurança e Robustez

### 7.1 Credenciais armazenadas em texto plano no `.env`

**Problema atual:**  
`ADAPTA_EMAIL` e `ADAPTA_SENHA` são salvas em texto plano no arquivo `.env`. Qualquer pessoa com acesso ao sistema de arquivos lê as credenciais trivialmente. Embora o `.gitignore` deva excluir o `.env`, acidentes acontecem.

**Por que melhorar:**  
Credenciais são dados sensíveis. Vazar a senha do Adapta.org expõe os projetos e dados dos clientes da agência.

**Como implementar:**  
**Opção A (Simples):** Usar o `keyring` do sistema operacional:

```python
import keyring

# Salvar
keyring.set_password("mediarats-artgen", email, senha)

# Ler
senha = keyring.get_password("mediarats-artgen", email)
```

O `keyring` no Windows usa o Windows Credential Manager. A senha nunca toca o disco em texto plano.

**Opção B (Intermediária):** Criptografar com `cryptography.fernet`:

```python
from cryptography.fernet import Fernet

# Gerar chave uma vez e salvar em local seguro
chave = Fernet.generate_key()
f = Fernet(chave)
senha_cifrada = f.encrypt(senha.encode())
```

**Impacto esperado:** Credenciais protegidas mesmo com acesso físico ao disco.  
**Dependências técnicas:** `keyring` ou `cryptography` (adicionar ao `requirements.txt`).  
**Prioridade:** **Alta**

---

### 7.2 Senha pode vazar em logs

**Problema atual:**  
Embora não haja log explícito da senha, mensagens de debug em `adapta_generator.py` podem incluir a URL completa ou parâmetros de requisição que contenham dados sensíveis. Mais crítico: se uma exceção incluir o conteúdo do campo `input[type=password]`, essa informação pode ir para `artgen.log`.

**Como implementar:**  
Adicionar um filtro de log que mascara credenciais:

```python
import re

class SensitiveFilter(logging.Filter):
    PATTERNS = [
        (re.compile(r'ADAPTA_SENHA=\S+'), 'ADAPTA_SENHA=***'),
        (re.compile(r'password["\s:=]+\S+', re.I), 'password=***'),
    ]
    
    def filter(self, record):
        for pattern, replacement in self.PATTERNS:
            record.msg = pattern.sub(replacement, str(record.msg))
        return True
```

**Impacto esperado:** Logs seguros mesmo em ambientes compartilhados.  
**Prioridade:** **Alta**

---

### 7.3 Sem backup antes de operações destrutivas na planilha

**Problema atual:**  
`ExcelWriter.remover_solicitacao` e `ExcelWriter.remover_cliente` deletam dados permanentemente sem criar backup prévio. Uma falha de disco durante `wb.save()` pode corromper a planilha inteira.

**Como implementar:**  
Criar backup automático antes de qualquer escrita destrutiva:

```python
import shutil

def _backup_planilha(self) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = self.caminho.parent / f".bak_{ts}_{self.caminho.name}"
    shutil.copy2(self.caminho, destino)
    return destino
```

Chamar `_backup_planilha()` no início de `remover_solicitacao` e `remover_cliente`. Manter apenas os 3 backups mais recentes para não encher o disco.

**Impacto esperado:** Recuperação possível em caso de falha; proteção contra erro humano.  
**Prioridade:** **Alta**

---

### 7.4 Sem validação de entrada nos diálogos

**Problema atual:**  
Os diálogos `ClientesDialog` e `CriarProtocoloDialog` possuem validação parcial. O campo de código do cliente aceita qualquer string sem verificar caracteres especiais ou injeção de fórmulas Excel (como `=CMD()`, `=HYPERLINK()`), o que pode causar problemas ao abrir o arquivo em Excel.

**Como implementar:**  
Adicionar validação de entrada rigorosa:

```python
def _validar_codigo(self, codigo: str) -> Optional[str]:
    if not re.match(r'^[A-Za-z]{2,6}$', codigo):
        return "Código deve ter 2-6 letras (sem números ou símbolos)."
    if codigo.upper() in self._codigos_existentes:
        return f"Código '{codigo}' já existe."
    return None  # válido
```

Adicionalmente, sanitizar qualquer valor antes de salvar na planilha para evitar injeção de fórmulas.

**Impacto esperado:** Dados consistentes; proteção contra erros sutis.  
**Prioridade:** **Média**

---

### 7.5 `WebDriver.wait(3000)` sem garantia de encerramento

**Problema atual:**  
Em `MainWindow.closeEvent`:
```python
self._worker.cancelar()
self._worker.wait(3000)
```
O `wait(3000)` espera até 3 segundos. Se o worker estiver preso em um `time.sleep()` no meio do Selenium, o processo Python encerra sem que o driver seja fechado, deixando processos Chrome/Edge/Firefox órfãos.

**Como implementar:**  
Forçar encerramento após timeout:

```python
self._worker.cancelar()
if not self._worker.wait(5000):  # 5 segundos
    logger.aviso("Worker não terminou no tempo esperado. Forçando encerramento.")
    self._worker.terminate()

if self._handler:
    try:
        self._handler.fechar()
    except Exception:
        pass
```

**Impacto esperado:** Sem processos de navegador órfãos após fechamento da aplicação.  
**Prioridade:** **Média**

---

## 8. Melhorias de Experiência do Usuário

### 8.1 Sem notificação ao concluir geração

**Problema atual:**  
A única notificação de conclusão é um `QMessageBox.information` que aparece sobre a janela principal. Se o usuário estiver em outra janela ou tela, não percebe a conclusão.

**Como implementar:**  
Adicionar notificação do sistema operacional usando `plyer` ou a API nativa do Windows:

```python
from plyer import notification

notification.notify(
    title="Media Rats Artgen",
    message=f"{sol.protocolo} — {len(caminhos)} arte(s) gerada(s)!",
    app_icon="logomr.ico",
    timeout=10,
)
```

Alternativamente, piscar o ícone na barra de tarefas do Windows:

```python
from PyQt6.QtWidgets import QApplication
QApplication.alert(self, 0)  # pisca até focar
```

**Impacto esperado:** Usuário notificado sem precisar monitorar a janela continuamente.  
**Dependências técnicas:** `plyer` (opcional, adicionar ao `requirements.txt`).  
**Prioridade:** **Média**

---

### 8.2 Fluxo de login manual confuso

**Problema atual:**  
Quando o login automático falha ou não está configurado, o sistema exibe um `QMessageBox` com instruções. O usuário precisa: (1) fechar a caixa de diálogo, (2) ir ao navegador, (3) fazer login, (4) voltar à aplicação, (5) clicar em "Iniciar Geração" novamente. Não há indicação visual de que a aplicação está aguardando o login.

**Como implementar:**  
Adicionar um estado visual de "aguardando login" na barra de status e um botão dedicado "Já fiz o login — continuar":

```python
def _on_login_necessario(self):
    self._handler = self._worker.handler
    self._atualizar_status("Aguardando login manual no navegador...", "pausado")
    self._controles.set_estado_aguardando_login()
    # Botão "Continuar após login" aparece nos controles
```

**Impacto esperado:** Fluxo de login muito mais claro e sem risco de erro.  
**Prioridade:** **Média**

---

### 8.3 Sem histórico de gerações concluídas acessível na UI

**Problema atual:**  
Após uma geração, o registro vai para a aba `AVALIACAO_DETALHADA` da planilha, mas não há como visualizar esse histórico dentro da própria aplicação sem abrir o Excel.

**Como implementar:**  
Adicionar uma aba "Histórico" no painel principal, lida da aba `AVALIACAO_DETALHADA`, com colunas: Protocolo, Cliente, Data, Nº de Artes, Pasta.

**Impacto esperado:** Visibilidade do trabalho realizado sem sair da aplicação.  
**Prioridade:** **Baixa**

---

### 8.4 `QMessageBox` de confirmação de cancelamento desnecessariamente bloqueante

**Problema atual:**  
Ao cancelar a geração, aparece um `QMessageBox.question` que bloqueia a UI enquanto o navegador continua executando. O usuário pode não conseguir interagir com o log enquanto aguarda sua decisão.

**Como implementar:**  
Substituir por um painel de confirmação não-modal integrado à interface, ou pelo menos garantir que o cancelamento seja mais responsivo usando `QMessageBox` com flags não-bloqueantes.

**Prioridade:** **Baixa**

---

### 8.5 Sem indicador de progresso ao carregar planilha

**Problema atual:**  
Ao clicar em "Recarregar", a interface congela brevemente enquanto a planilha é lida. Em planilhas grandes, esse congelamento pode durar vários segundos sem nenhum indicador visual.

**Como implementar:**  
Mover a leitura da planilha para uma thread (`QThread`) com sinal de progresso, e exibir um cursor de espera ou barra de progresso indeterminada:

```python
QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
try:
    # leitura
finally:
    QApplication.restoreOverrideCursor()
```

**Impacto esperado:** Interface nunca congela visualmente.  
**Prioridade:** **Média**

---

## 9. Melhorias de Escalabilidade

### 9.1 Planilha Excel como banco de dados — limitações para crescimento

**Problema atual:**  
A planilha Excel é o único repositório de dados do sistema: clientes, solicitações, avaliações. Com o tempo, a aba `AVALIACAO_DETALHADA` cresce indefinidamente (10 linhas por protocolo). Com 100 clientes e 50 solicitações/mês cada, em um ano seriam 60.000+ linhas, tornando a leitura muito lenta.

**Por que melhorar:**  
Excel não é um banco de dados. Não suporta concorrência, não tem índices, não tem transações atômicas confiáveis.

**Como implementar:**  
**Fase 1 (curto prazo):** Manter Excel para entrada de dados mas mover histórico para SQLite:

```python
# Em vez de AVALIACAO_DETALHADA na planilha:
import sqlite3

def registrar_avaliacao_db(self, solicitacao, caminhos):
    with sqlite3.connect("artgen.db") as conn:
        conn.executemany(
            "INSERT INTO avaliacoes VALUES (?,?,?,?,?,?,?)",
            [(sol.protocolo, sol.cliente, ...) for sol in ...]
        )
```

**Fase 2 (médio prazo):** Migrar clientes e solicitações para SQLite também, mantendo Excel como formato de import/export.

**Impacto esperado:** Performance estável independente do volume de dados; suporte a consultas complexas.  
**Dependências técnicas:** `sqlite3` (stdlib), sem novas dependências externas.  
**Prioridade:** **Média** (curto prazo) / **Alta** (médio prazo)

---

### 9.2 Sem suporte a múltiplos perfis de agência

**Problema atual:**  
O sistema tem um único arquivo `.env`, uma única planilha e uma única pasta `output`. Não há como operar para múltiplas agências ou múltiplos operadores no mesmo ambiente.

**Como implementar:**  
Implementar o conceito de "workspace" ou "perfil":

```python
# settings.json
{
    "perfis": {
        "agencia_a": {
            "planilha": "./planilha/agencia_a.xlsx",
            "output": "./output/agencia_a/",
            "url_adapta": "https://www.adapta.org"
        }
    },
    "perfil_ativo": "agencia_a"
}
```

Adicionar seletor de perfil na barra de status ou no menu.

**Impacto esperado:** Uma única instalação suportando múltiplos clientes/agências sem conflito.  
**Prioridade:** **Baixa**

---

### 9.3 Acoplamento forte ao Adapta.org

**Problema atual:**  
Todo o módulo `bot/` é construído especificamente para o Adapta.org. Os seletores, a lógica de navegação, o `chat_mapping.py` — tudo é específico para esse site. Se a agência precisar usar outro gerador de imagens (Midjourney, Adobe Firefly, Leonardo AI), seria necessário reescrever o bot do zero.

**Como implementar:**  
Definir uma interface abstrata para geradores:

```python
# bot/base_generator.py
from abc import ABC, abstractmethod

class BaseGenerator(ABC):
    @abstractmethod
    def acessar(self, email: str, senha: str) -> bool: ...
    
    @abstractmethod
    def gerar_arte(self, prompt: str, numero: int) -> Optional[Path]: ...
    
    @abstractmethod
    def fechar(self) -> None: ...

# bot/adapta_generator.py implementa BaseGenerator
class AdaptaGenerator(BaseGenerator): ...
```

Selecionar o gerador via `Config.GERADOR = "adapta"` (com enum).

**Impacto esperado:** Suporte a múltiplos geradores sem alterar a UI ou a lógica de negócio.  
**Prioridade:** **Baixa** (agora) / **Alta** (quando houver segundo gerador)

---

### 9.4 Ausência de exportação de relatórios

**Problema atual:**  
Toda a informação de avaliação fica na planilha Excel, sem possibilidade de exportar relatórios formatados para compartilhar com clientes ou gestores.

**Como implementar:**  
Adicionar exportação em formatos alternativos:

- **CSV:** Simples, via `csv` stdlib a partir dos dados de `AVALIACAO_DETALHADA`
- **PDF:** Relatório de protocolo com thumbnails das imagens, usando `reportlab`
- **HTML:** Galeria de imagens geradas por protocolo

**Impacto esperado:** Facilita prestação de contas e comunicação com clientes.  
**Prioridade:** **Baixa**

---

## 10. Melhorias Futuras / Roadmap

### 10.1 Banco de dados SQLite como repositório central

**Visão:** Migrar completamente de Excel para SQLite como repositório de dados estruturados. Manter o Excel apenas como canal de importação/exportação para usuários que preferem editar em planilhas.

**Benefícios:** Queries com JOINs entre clientes e solicitações; índices para busca rápida; integridade referencial; backup por cópia de arquivo.

**Estimativa:** 2-3 semanas de migração incluindo testes.

---

### 10.2 Interface web complementar

**Visão:** Expor uma API REST local (FastAPI/Flask) para que outra ferramenta (dashboard web, app mobile) possa consultar status de geração e resultados.

```python
# api/server.py com FastAPI
@app.get("/solicitacoes")
def listar_solicitacoes():
    return reader.ler_solicitacoes(apenas_pendentes=False)
```

**Benefícios:** Monitoramento remoto; integração com outras ferramentas da agência.

---

### 10.3 Sistema de aprovação e rejeição de artes

**Visão:** Após geração, mostrar as imagens geradas em um painel de aprovação. O operador aprova ou rejeita cada arte. Artes rejeitadas podem ser regeradas automaticamente com prompt refinado.

**Fluxo:**
```
Gerado → Aprovação → Aprovado / Rejeitado (regenerar)
```

**Impacto:** Fluxo de trabalho completo dentro da aplicação; menos round-trips ao Excel.

---

### 10.4 Templates de prompt reutilizáveis

**Visão:** Biblioteca de templates de prompt por nicho de mercado (saúde, moda, tecnologia, etc.) que o operador pode selecionar e personalizar ao criar um protocolo.

**Implementação:** Arquivo `templates/prompts.json` com estrutura editável pela UI.

---

### 10.5 Integração com webhooks / notificações externas

**Visão:** Ao concluir uma geração, o sistema pode enviar uma notificação para:
- URL webhook configurável (Slack, Discord, Zapier)
- Email via SMTP
- Telegram Bot

**Implementação:** Listener de evento `geracao_concluida` com publishers plugáveis.

---

### 10.6 Versionamento de prompts

**Visão:** Registrar o histórico de versões de cada prompt gerado para um protocolo, permitindo comparação entre gerações e rastreabilidade de qual prompt produziu qual resultado.

---

### 10.7 Suporte a múltiplos geradores de imagem

Conforme descrito em 9.3, implementar `BaseGenerator` e adapters para:
- Adapta.org (já existe)
- Adobe Firefly
- Leonardo AI
- Midjourney (via Discord bot ou API)

---

### 10.8 Modo CLI (Command Line Interface)

**Visão:** Permitir uso do sistema sem a UI gráfica para execução em servidores headless ou pipelines CI:

```bash
python artgen.py --protocolo DUDE#5 --headless --sem-confirmacao
python artgen.py --processar-fila --data-hoje
```

**Dependências técnicas:** Separação completa da lógica de negócio da UI (pré-requisito: item 3.4).

---

## 11. Priorização Recomendada por Etapas

### Etapa 1 — Estabilidade e Segurança Imediata
*Prazo sugerido: 1-2 semanas*

| ID | Melhoria | Prioridade |
|----|----------|------------|
| 1.4 | Validação de prompt antes do envio | Alta |
| 1.5 | Corrigir socket sem fechamento | Média |
| 2.1 | `read_only=True` na leitura Excel | Alta |
| 2.3 | Sleeps bloqueantes → interrompíveis | Alta |
| 3.5 | Logger via sinais PyQt6 | Alta |
| 4.4 | Rotação de logs | Média |
| 7.1 | Credenciais no keyring | Alta |
| 7.2 | Filtro de dados sensíveis nos logs | Alta |
| 7.3 | Backup antes de operações destrutivas | Alta |
| 7.5 | Encerramento correto do worker ao fechar | Média |

---

### Etapa 2 — Produtividade e Qualidade de Uso
*Prazo sugerido: 2-4 semanas*

| ID | Melhoria | Prioridade |
|----|----------|------------|
| 1.1 | Processar fila completa automaticamente | Alta |
| 5.2 | Filtro e busca na tabela de fila | Alta |
| 6.1 | Botão "Processar Fila Completa" | Alta |
| 6.2 | Retry automático por arte | Alta |
| 4.3 | Testes automatizados básicos (utils + excel) | Alta |
| 8.1 | Notificação de sistema ao concluir | Média |
| 8.2 | Fluxo de login manual melhorado | Média |
| 8.5 | Indicador de progresso ao carregar planilha | Média |

---

### Etapa 3 — Qualidade de Código e Arquitetura
*Prazo sugerido: 1-2 meses*

| ID | Melhoria | Prioridade |
|----|----------|------------|
| 3.1 | Quebrar `adapta_generator.py` em módulos | Alta |
| 3.3 | Mover `GeracaoWorker` para módulo próprio | Média |
| 3.4 | Implementar camada de serviço | Média |
| 4.1 | Centralizar `STATUS_CORES` | Média |
| 4.2 | Externalizar seletores CSS | Média |
| 5.1 | Centralizar estilos em `gui/theme.py` | Média |
| 5.4 | Limite de linhas no painel de log | Média |
| 2.2 | Cache de leitura da planilha | Média |
| 2.4 | Combinar escritas na planilha | Média |

---

### Etapa 4 — Escalabilidade e Recursos Avançados
*Prazo sugerido: 3-6 meses*

| ID | Melhoria | Prioridade |
|----|----------|------------|
| 9.1 | Migração para SQLite | Média → Alta |
| 5.5 | Preview de imagens na UI | Média |
| 8.3 | Histórico de gerações na UI | Baixa |
| 9.3 | Interface abstrata para geradores | Baixa |
| 3.2 | Refatorar `Config` como instância | Média |
| 10.1 | SQLite como repositório central | Alta |
| 10.8 | Modo CLI | Baixa |

---

### Etapa 5 — Roadmap de Produto
*Prazo sugerido: 6+ meses*

| ID | Melhoria |
|----|----------|
| 10.2 | Interface web complementar |
| 10.3 | Sistema de aprovação de artes |
| 10.4 | Templates de prompt reutilizáveis |
| 10.5 | Webhooks e notificações externas |
| 10.6 | Versionamento de prompts |
| 10.7 | Suporte a múltiplos geradores de imagem |

---

## Notas Finais

Este documento representa uma análise estática do código-fonte. Algumas melhorias podem revelar complexidades adicionais durante a implementação. Recomenda-se:

1. **Manter um branch de desenvolvimento** para cada etapa, com PRs e revisão antes de mesclar ao principal.
2. **Implementar testes antes de refatorar** (Etapa 1, item 4.3) — especialmente para `excel/reader.py` e `utils/prompt_composer.py`, que são o coração do sistema.
3. **Priorizar estabilidade sobre features** — os itens da Etapa 1 e 2 têm maior retorno imediato.
4. **Manter retrocompatibilidade** com o formato da planilha existente em todas as mudanças, para não perder dados históricos.

---

*Documento gerado a partir de análise completa de todos os módulos da versão 1.0.0 do Media Rats Artgen.*  
*Próxima revisão recomendada: após conclusão da Etapa 2.*
