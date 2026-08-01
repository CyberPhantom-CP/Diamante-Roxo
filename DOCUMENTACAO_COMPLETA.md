# Diamante Roxo v4.10 — Documentação Completa

Sistema de automação para transmissão ao vivo baseado em OBS Studio.
Gerencia cenas, áudio, alertas e transições de forma autônoma.

---

## Sumário

1. [Visão Geral](#1-visão-geral)
2. [Arquitetura](#2-arquitetura)
3. [Fluxo de Execução](#3-fluxo-de-execução)
4. [Modos de Operação](#4-modos-de-operação)
5. [Sistema de Alertas](#5-sistema-de-alertas)
6. [Transições com Alerta Ativo](#6-transições-com-alerta-ativo)
7. [Cache e Otimizações](#7-cache-e-otimizações)
8. [Arquivos de Configuração](#8-arquivos-de-configuração)
9. [Estrutura de Funções](#9-estrutura-de-funções)
10. [GrampeadoOBS (Classe Principal)](#10-grampeadoobs-classe-principal)
11. [Dependências Externas](#11-dependências-externas)
12. [Como Usar](#12-como-usar)

---

## 1. Visão Geral

**Nome:** Diamante Roxo v4.7  
**Autor:** CyberPhantom (C.P.)  
**Função:** Automatizar transmissões ao vivo gerenciando OBS Studio, Streamer.bot, Mix It Up e Chatty.

O sistema opera em três modos principais:
- **FILMES:** Reprodução de mídia com sistema de censura por tempo e saltos pós-créditos.
- **RERUN:** Retransmissão ao vivo com contagem regressiva e fontes dinâmicas.
- **ESTUDO:** Fluxo híbrido — transmissão manual com estudo, transição automática para FILMES/RERUN via `iniciar_midias`.

Suporta duas plataformas:
- **Twitch:** todos os apps são iniciados (Mix It Up, Chatty, Streamer.bot, OBS).
- **Kick:** apenas Streamer.bot e OBS são iniciados.

A configuração é feita inteiramente pelo arquivo `Painel_de_Controle.txt`, permitindo que o sistema rode sozinho sem intervenção manual durante a live.

---

## 2. Arquitetura

```
Painel_de_Controle.txt  (configuração)
         │
         ▼
   Main Loop ─── schedule.run_pending()  (tarefas agendadas)
          │
          ├── Inicialização: OBS, Streamer.bot, Mix It Up, Chatty
          ├── Conexão OBS WebSocket
          │      ├── ReqClient (comandos)
          │      └── EventClient (eventos) → GrampeadoOBS
          │
          ├── Fluxo Normal (modo_conteudo = filmes | rerun)
          │         │
          │         ▼
          │   aba_geral() → aba_entrada() → aba_inicio()
          │         │
          │   ┌─────┴─────┐
          │   ▼           ▼
          │ aba_midias()  aba_rerun()
          │ (FILMES)      (RERUN)
          │   │           │
          │   ▼           ▼
          │ aba_pausa()  horario_de_rerun()
          │ (noturna)    (contagem regressiva)
          │   │           │
          │   └─────┬─────┘
          │         ▼
          │   aba_raid() → aba_final() → stop_sistema()
          │
          └── Fluxo Estudo (modo_conteudo = estudo)
                    │
                    ▼
              Você inicia OBS + transmissão manual
              cena MÍDIAS com EV BRADESCO + WORD_VS
                    │
                    ▼ (agendado: iniciar_midias)
              iniciar_midias_direto()
                    │
                    ▼
              Desliga EV BRADESCO + WORD_VS
              Liga FILMES/GIF/SESSÃO ID (ou RERUN)
                    │
              ┌─────┴─────┐
              ▼           ▼
          aba_midias()  aba_rerun()
          (FILMES)      (RERUN)
```

Durante todo o ciclo, o **GrampeadoOBS** (EventClient) escuta eventos do OBS em segundo plano:
- **on_current_program_scene_changed:** detecta troca manual de cena.
- **on_input_volume_meters:** monitora volume do MSG_PIX para detectar alertas.
- **on_input_mute_state_changed:** trata mutar/desmutar do mixer.

---

## 3. Fluxo de Execução

### 3.1. Inicialização

1. **Caminhos do script** são resolvidos dinamicamente (suporta .py e .exe).
2. **Localização dos softwares** é feita por caminhos conhecidos de instalação (ProgramFiles, AppData, LocalAppData).
3. **Log** é aberto no arquivo `relatório_<data>.log`.
4. **Trava de segurança** verifica se `executar_sistema = yes` no Painel_de_Controle.txt.

### 3.2. Scheduler (Agendamento)

O arquivo `Painel_de_Controle.txt` define horários para cada ação:

| Chave | O que faz | Plataforma |
|---|---|---|---|
| `plataforma` | `twitch` (todos) ou `kick` (só OBS + Streamer.bot) | - |
| `mixitup` | Inicia Mix It Up | Só Twitch |
| `streamerbot` | Inicia Streamer.bot | Ambas |
| `obs64studio` | Inicia OBS Studio | Ambas |
| `chatty` | Inicia Chatty | Só Twitch |
| `minimizar_janelas` | Minimiza todos os apps | - |
| `conectar_obs` | Conecta ao OBS WebSocket | - |
| `start_sistema` | Inicia transmissão/gravação | - |
| `retornar_midias` | Retorna de PAUSA para MÍDIAS | - |

O scheduler verifica o arquivo a cada 5 segundos. Se houver alteração, recarrega tudo.

### 3.3. Cenas (Sequência)

```
ENTRADA (9s) → INÍCIO (7min05s) → MÍDIAS (loop filmes) → PAUSA (noturna, opcional)
                                  → RERUN (contagem regressiva)
                                  → RAIDA (11min10s) → FINAL (5min10s) → ENCERRAMENTO
```

Cada cena pode ser interrompida manualmente pelo usuário no OBS. O sistema detecta e chama `rotear_pulo()` para redirecionar ao fluxo correto.

---

## 4. Modos de Operação

### 4.1. Modo FILMES

Controlado por `modo_conteudo = filmes` no painel.

- Lê `tempo_duracao.txt` com a lista de durações dos filmes.
- Para cada filme:
  - Carrega censuras de `controle_censura.txt` (ativa/desativa fontes CENSURA/TARJA em timestamps específicos).
  - Monitora cursor da mídia via `get_media_input_status`.
  - Detecta **skip manual** do usuário (avanço > 15s).
  - Executa **saltos pós-créditos** automáticos configurados no `tempo_duracao.txt`.
  - Verifica **pausa noturna** (23h às 6h) entre filmes.
- Ao final de todos os filmes, avança para RAIDA.

**Controle de visibilidade das fontes na cena MÍDIAS:**

| Ligadas | Desligadas |
|---|---|---|
| GIF | WEBCAM |
| STREAMER OFF | STREAMER ON |
| FILMES | RERUN |
| SESSÃO ID | SPOTIFY |
|  | CENSURA |
|  | TARJA |
|  | EV BRADESCO |
|  | WORD_VS |

### 4.2. Modo RERUN

Controlado por `modo_conteudo = rerun` no painel.

- Apenas fontes RERUN, SPOTIFY e STREAMER OFF ficam visíveis. EV BRADESCO e WORD_VS são desligadas.
- Exibe contagem regressiva ao vivo até o horário configurado em `rerun_horario_final`.
- Detecta alterações em tempo real nos parâmetros do painel (dias, horário).
- Ao finalizar, redireciona conforme `saida_rerun`:
  - `raid` → aba_raid()
  - `reset` → resetar_fluxo() (recomeça do início)
  - `final` → aba_final()

### 4.3. Modo ESTUDO

Controlado por `modo_conteudo = estudo` no painel.

- Fluxo híbrido para dias de estudo presencial:
  - Você abre OBS + transmissão manualmente (cena MÍDIAS com fontes EV BRADESCO e WORD_VS visíveis).
  - `conectar_obs` conecta o WebSocket no horário agendado.
  - `start_sistema` é **ignorado** — não força ENTRADA/INÍCIO.
  - `iniciar_midias` (agendado separadamente) dispara a transição:
    1. Garante que a cena MÍDIAS está ativa.
    2. Desliga EV BRADESCO e WORD_VS.
    3. Liga FILMES + GIF + SESSÃO ID (ou RERUN + SPOTIFY).
    4. Inicia o loop normal de filmes/rerun.
- Em dias sem estudo, basta mudar para `modo_conteudo = filmes` ou `rerun` — `iniciar_midias` é ignorado, `start_sistema` funciona normalmente.

---

## 5. Sistema de Alertas

### 5.1. Detecção

A classe `GrampeadoOBS` monitora o volume de `MSG_PIX` (definido em `fontes_alertas`).
Quando o volume ultrapassa o limite `0.00316` (cerca de -50dB), o alerta é disparado.

### 5.2. Ducking (Redução de Áudio)

Quando um alerta é detectado:

- **Modo FILMES na cena MÍDIAS:**
  - PAUSA no filme atual (via `trigger_media_input_action`).
  
- **Outras cenas / modos:**
  - Para cada fonte listada em `fontes_por_cena`, salva o volume original no "cofre" (`volumes_originais`).
  - Reduz o volume para -30dB (`0.031622` multiplicador).

**Fontes por cena (NUNCA sofrem ducking):**

| Cena | Fontes que sofrem ducking |
|---|---|
| INÍCIO | MÚSICAS |
| MÍDIAS | SPOTIFY |
| PAUSA | SPOTIFY |

A fonte `MSG_PIX` (definida em `fontes_alertas`) é automaticamente excluída do ducking mesmo se listada em `fontes_por_cena`.

### 5.3. Timer de Retorno

Quando o volume do `MSG_PIX` volta ao normal:
- Um timer de **3 segundos** é iniciado.
- Se outro alerta chegar antes do timer finalizar, o timer é **cancelado e reiniciado**.
- Se o timer completar 3 segundos, o sistema restaura todos os volumes com **fade-in de 2 segundos** em 8 passos.

### 5.4. Tratamento de Mixer Mutado

Se o usuário mutar o mixer do `MSG_PIX` no OBS:
- O sistema para imediatamente o resgate.
- Restaura todos os volumes.
- Quando desmutar, reativa os sensores.

---

## 6. Transições com Alerta Ativo

Se o usuário trocar de cena manualmente enquanto um alerta está em andamento:

1. **Fontes que saíram da cena anterior:** têm o volume restaurado imediatamente (fade-out é cancelado).
2. **Modo FILMES:** se destino = MÍDIAS, o filme é pausado (duas chamadas consecutivas para confiabilidade).
3. **Modo RERUN:** fontes que entraram na nova cena recebem fade-out.
4. Ao finalizar o alerta, o sistema chama `_finalizar_transicao()` que:
   - Se for FILMES e cena = MÍDIAS: dá PLAY no filme.
   - Limpa o estado de transição.

**Segurança:** se o usuário tentar rotear para RAIDA ou FINAL manualmente com alerta ativo, o sistema aguarda o alerta terminar antes de prosseguir.

---

## 7. Cache e Otimizações

### 7.1. Cache de Fontes por Cena

`_cache_fontes_cena` armazena o resultado de `_obter_fontes_cena()` (filtragem de `fontes_por_cena` removendo `fontes_alertas`).  
O cache é limpo a cada troca de cena.

### 7.2. Cache de Visibilidade

`_vis_cache` armazena `scene_items` retornados por `get_scene_item_list()` para cada cena.  
Em uma transição com 12 chamadas de `visibilidade_fonte()`, a consulta OBS é feita apenas **1 vez** em vez de 12.  
Cache é limpo no início de `aba_midias()` e `aba_rerun()`.

### 7.3. Fade com 8 Passos

Fades de volume usam 8 passos em vez de 15, reduzindo chamadas à API do OBS em cerca de 47%.

### 7.4. Polling do Painel

O arquivo de configuração é verificado a cada 5 segundos (em vez de 1s), reduzindo leituras de disco em 80%.

### 7.5. Polling dos Loops de Detecção

Os sleeps internos foram ajustados para reduzir carga na CPU durante a transmissão:

| Loop | Antes | Depois | Economia |
|---|---|---|---|
| Detecção de filmes (`esperar_com_deteccao`) | 0.2s | 0.5s | ~10.800 chamadas/hora a menos |
| Pausa noturna (`aba_pausa`) | 2s | 3s | 600 leituras OBS/hora a menos |
| Relógio RERUN (`horario_de_rerun`) | 0.5s | 1s | 3.600 prints/hora a menos |

---

## 8. Arquivos de Configuração

### 8.1. Painel_de_Controle.txt

Localizado na pasta `TWITCH` (pai da pasta `Script`).

```
executar_sistema      = yes              # Trava de segurança
modo_sistema          = live / gravar    # Modo de transmissão
plataforma            = twitch / kick    # Twitch (todos apps) ou Kick (só OBS + Streamer.bot)
modo_conteudo         = filmes / rerun / estudo   # Modo de operação
modo_destino          = filmes / rerun            # Destino do disparo iniciar_midias (quando modo=estudo)
modo_raid             = final / rerun    # Destino após RAID
saida_rerun           = final / raid / reset
rerun_dias            = 1                # Dias para encerramento RERUN
rerun_horario_final   = 23:59:59         # Horário alvo do RERUN
obs_host              = 192.168.1.x      # IP do OBS
obs_port              = 4455             # Porta WebSocket
obs_password          = ****             # Senha WebSocket
mixitup               = HH:MM:SS         # Horário para iniciar
streamerbot           = HH:MM:SS
obs64studio           = HH:MM:SS
chatty                = HH:MM:SS
minimizar_janelas     = HH:MM:SS
conectar_obs          = HH:MM:SS
start_sistema         = HH:MM:SS          # Ignorado se modo=estudo
retornar_midias       = HH:MM:SS
iniciar_midias        = HH:MM:SS          # Só usado se modo=estudo
```

### 8.2. tempo_duracao.txt

Lista de durações de filmes, uma por linha. Pode incluir saltos pós-crédito:

```
02:07:11|01:55:00>02:02:00
01:45:30
02:15:00|02:00:00>02:10:00;02:10:00>02:12:30
```

Formato: `DURAÇÃO|GATILHO>DESTINO;GATILHO>DESTINO...`

### 8.3. controle_censura.txt

Censura por tempo para cada filme:

```
True|00:05:00>00:07:30>TARJA;00:10:00>00:12:00>CENSURA
False
True|00:01:00>00:03:00>TARJA,CENSURA
```

Formato: `STATUS|INICIO>FIM>FONTE;INICIO>FIM>FONTE...`  
STATUS = True ativa as censuras do filme, False pula.  
FONTE pode ser uma ou várias separadas por vírgula.

### 8.4. relatório_<data>.log

Gerado automaticamente na pasta `Script` com timestamps:
```
<DATA> - INFO - <mensagem>
```

---

## 9. Estrutura de Funções

### 9.1. Utilitárias de Sistema

| Função | Descrição |
|---|---|
| `log(msg)` | Print + grava no arquivo de log |
| `verificar_app_start(nome)` | Checa se processo está rodando |
| `start_mixitup()` | Inicia Mix It Up (localização dinâmica + subprocess.Popen) |
| `start_streamerbot()` | Inicia Streamer.bot (localização dinâmica + subprocess.Popen) |
| `start_obs64studio()` | Inicia OBS Studio (localização dinâmica + subprocess.Popen) |
| `start_chatty()` | Inicia Chatty (localização dinâmica + subprocess.Popen) |
| `minimizar_janelas()` | Minimiza todos os 4 apps via pywinauto |

### 9.2. OBS WebSocket

| Função | Descrição |
|---|---|
| `conectar_obs()` | Cria ReqClient + GrampeadoOBS |
| `trocar_cena(nome)` | Muda cena programática |
| `cena_ativa_obs()` | Retorna nome da cena atual |
| `ajustar_volume_seguro(fonte, vol)` | Ajusta volume com clamp de segurança |

### 9.3. Visibilidade e Texto

| Função | Descrição |
|---|---|
| `limpar_cache_vis()` | Limpa cache de scene items |
| `visibilidade_fonte(cena, fonte, visivel)` | Liga/desliga fonte (com cache + suporte a grupos) |
| `id_sessao(texto)` | Atualiza texto SESSÃO ID |
| `id_live(texto)` | Atualiza texto ID LIVE |

### 9.4. Cenas (Fluxo Principal)

| Função | Descrição |
|---|---|
| `aba_entrada()` | Cena de entrada (9s) → INÍCIO |
| `aba_inicio()` | Cena inicial (7min05s) → MÍDIAS ou RERUN |
| `aba_midias()` | Loop de filmes com censura + skip |
| `aba_rerun()` | Retransmissão com contagem regressiva |
| `aba_pausa()` | Pausa noturna até troca manual |
| `aba_raid()` | Cena de raide (11min10s) |
| `aba_final()` | Cena final (5min10s) → encerramento |
| `aba_geral()` | Ponto de entrada do thread (fluxo normal) |
| `iniciar_midias_direto()` | Gatilho direto para MÍDIAS (fluxo estudo) |
| `rotear_pulo()` | Roteador de troca manual de cena |

### 9.5. Mídia e Tempo

| Função | Descrição |
|---|---|
| `esperar(tempo, cena, ...)` | Wrapper para `esperar_com_deteccao` |
| `esperar_com_deteccao(...)` | Loop principal de detecção (skip, censura, salto, pausa) |
| `arquivo_tempo()` | Lê `tempo_duracao.txt` |
| `skip_videos(fonte)` | Avança para próxima mídia |
| `carregar_censuras_do_filme(i)` | Lê regras de censura do filme i |
| `horario_de_rerun()` | Contagem regressiva do RERUN |

### 9.6. Controle

| Função | Descrição |
|---|---|
| `start_sistema()` | Conecta OBS + inicia stream/record |
| `iniciar_fluxo()` | Marca ID LIVE + dispara aba_geral em thread |
| `resetar_fluxo()` | Reinicia o fluxo |
| `stop_sistema()` | Para stream/record + encerra |
| `verificar_agendamento()` | Monitora Painel_de_Controle.txt + agenda tarefas (condiciona `iniciar_midias` / `start_sistema` conforme `modo_conteudo`) |
| `auto_retorno_midias()` | Retorno automático da PAUSA |

---

## 10. GrampeadoOBS (Classe Principal)

Subclasse de `EventClient` (obsws_python).  
Gerencia toda a resposta a eventos do OBS em tempo real.

### 10.1. Atributos

| Atributo | Tipo | Descrição |
|---|---|---|
| `fontes_alertas` | list | Fontes que disparam alerta (padrão: `["MSG_PIX"]`) |
| `fontes_por_cena` | dict | Mapeamento cena → fontes para ducking |
| `cena_atual` | str | Cena atual no OBS |
| `resgate_em_andamento` | bool | True durante alerta ativo |
| `timer_retorno` | Timer | Timer de 3s para finalizar resgate |
| `volumes_originais` | dict | Volumes salvos antes do ducking (cofre) |
| `transicao` | dict | Estado da transição atual (se houver alerta) |
| `mixer_mutado` | bool | True se MSG_PIX está mutado |
| `_midia_pausada_pelo_alerta` | bool | True se FILMES foi pausado pelo alerta |

### 10.2. Event Handlers

| Método | Evento OBS | Ação |
|---|---|---|
| `on_current_program_scene_changed` | Cena trocada | Gerencia transição com alerta |
| `on_input_volume_meters` | Volume do áudio mudou | Detecta alerta e faz ducking |
| `on_input_mute_state_changed` | Estado de mute | Trata mutar/desmutar do MSG_PIX |

### 10.3. Métodos de Ação

| Método | Descrição |
|---|---|
| `aplicar_acao_inicial()` | Pausa mídia ou reduz volume (ducking) |
| `finalizar_resgate_com_seguranca()` | Restaura volumes + retoma mídia |
| `executar_efeito_fade(...)` | Fade suave em 8 passos |
| `_obter_fontes_cena(cena)` | Retorna fontes duckáveis (exclui alertas) |

### 10.4. Helpers de Transição

| Método | Descrição |
|---|---|
| `_iniciar_transicao_locked(...)` | Registra nova transição (com lock) |
| `_cancelar_transicao_locked()` | Cancela transição atual |
| `_aplicar_transicao_filmes(...)` | Pausa FILMES durante transição |
| `_aplicar_transicao_rerun(...)` | Fade-out de fontes que entraram na cena |
| `_finalizar_transicao()` | Finaliza: retoma mídia + limpa estado |

---

## 11. Dependências Completas

### 11.1. Python (linguagem)

Python 3.10+ instalado e no PATH.

### 11.2. Pacotes Python (`pip install`)

```bash
pip install schedule psutil pywinauto obsws_python
```

| Pacote | Uso |
|---|---|
| `schedule` | Agendamento de tarefas (start_sistema, iniciar_midias, etc.) |
| `psutil` | Controle de prioridade de processo, gerenciamento de processos |
| `pywinauto` | Automação de janelas (minimizar aplicativos) |
| `obsws_python` | Controle do OBS via WebSocket v5 (cenas, fontes, áudio, stream) |

### 11.3. Node.js

Node.js 18+ instalado e no PATH. Usado exclusivamente pelo relay.

### 11.4. Pacote Node.js (`npm install`)

Dentro da pasta `TWITCH/Script/`:

```bash
npm install node-media-server
```

| Pacote | Uso |
|---|---|
| `node-media-server` | Servidor RTMP local na porta 1936 (OBS → relay → Kick) |

### 11.5. FFmpeg

FFmpeg instalado e no PATH. Usado para:
- Push do stream local para o Kick (`relay.js`)
- Teste de conexão com o Kick antes de iniciar (`testar_conexao_kick()`)

### 11.6. Softwares Gerenciados (iniciados pelo script)

| Software | Executável | Função |
|---|---|---|
| **OBS Studio** | `obs64.exe` | Transmissão, gravação, cenas, fontes |
| **Streamer.bot** | `Streamer.bot.exe` | Eventos, comandos e alertas da live |
| **Mix It Up** | `MixItUp.exe` | Chat, interatividade e comandos (Twitch) |
| **Chatty** | `Chatty.exe` | Cliente de chat com moderação (Twitch) |

### 11.7. Arquivos do Projeto (devem estar salvos)

| Arquivo | Pasta | Função |
|---|---|---|
| `Diamante Roxo.py` | `TWITCH/Script/` | Script principal |
| `relay.js` | `TWITCH/Script/` | Relay FFmpeg (Node.js) |
| `Relay (iniciar).bat` | `TWITCH/` | Atalho para iniciar relay manualmente |
| `Painel_de_Controle.txt` | `TWITCH/` | Configuração principal |
| `tempo_duracao.txt` | `TWITCH/` | Durações e saltos dos filmes |
| `controle_censura.txt` | `TWITCH/` | Regras de censura por filme |
| `DOCUMENTACAO_COMPLETA.md` | `TWITCH/` | Documentação completa |
| `JORNADA_DIAMANTE_ROXO.md` | `TWITCH/` | Histórico de versões |

### 11.8. Arquivos Gerados em Execução

| Arquivo | Pasta | Conteúdo |
|---|---|---|
| `relatório_<data>.log` | `TWITCH/Script/` | Log da sessão |
| `relay.log` | `TWITCH/` | Log do relay |
| `relay_status.json` | `TWITCH/` | Status da conexão do relay |

### 11.9. Configuração OBS

| Arquivo | Caminho | Observação |
|---|---|---|
| `basic.ini` | `%APPDATA%/obs-studio/basic/profiles/GERAL/` | Perfil 1280x720, 30 FPS, CBR 4000 |
| `streamEncoder.json` | `%APPDATA%/obs-studio/basic/profiles/GERAL/` | x264 ultrafast, baseline |
| `global.ini` | `%APPDATA%/obs-studio/` | BrowserHWAccel=true, ProcessPriority=High |
| `KS.json` | `%APPDATA%/obs-studio/basic/scenes/` | Cena principal com 15 sources |

> **Dica:** Backupeie a pasta `%APPDATA%/obs-studio/` inteira. Contém perfil, cenas, fontes, configurações de áudio e encoding.

---

## 12. Como Usar

### 12.1. Primeira Configuração (do zero)

#### 12.1.1. Instalar Python

1. Acesse https://www.python.org/downloads/
2. Baixe a versão mais recente (3.12+ ou 3.13+)
3. Na instalação, **marque "Add Python to PATH"** (obrigatório)
4. Clique em "Install Now"
5. Verifique: abra o Prompt/Terminal e digite:
   ```bash
   python --version
   ```

#### 12.1.2. Instalar pacotes Python

```bash
pip install schedule psutil pywinauto obsws_python
```

#### 12.1.3. Instalar Node.js

1. Acesse https://nodejs.org/ (baixe a versão LTS)
2. Execute o instalador — marque todas as opções padrão (inclui PATH automaticamente)
3. Verifique:
   ```bash
   node --version
   npm --version
   ```

#### 12.1.4. Instalar pacote do relay

Na pasta `TWITCH/Script/`:

```bash
npm install node-media-server
```

#### 12.1.5. Instalar FFmpeg

1. Acesse https://ffmpeg.org/download.html
2. Clique em "Windows" → escolha um build (ex.: "gyan.dev" ou "BtbN")
3. Baixe o arquivo `.zip` (ex.: `ffmpeg-release-essentials.zip`)
4. Extraia para `C:\ffmpeg\`
5. Adicione ao PATH do sistema:
   - Tecla Windows → "Variáveis de Ambiente"
   - Em "Variáveis do sistema" → selecione `Path` → "Editar"
   - "Novo" → cole `C:\ffmpeg\bin`
   - OK em todas as janelas
6. Verifique (abra um NOVO terminal):
   ```bash
   ffmpeg -version
   ```

6. Configure o OBS Studio:
   - Ative o WebSocket em Ferramentas → WebSocket Server Settings.
   - Porta padrão: 4455 (ou configure no Painel de Controle).
   - Senha opcional.

7. Coloque todos os arquivos do projeto na estrutura correta:
   ```
   TWITCH/
   ├── Painel_de_Controle.txt
   ├── tempo_duracao.txt
   ├── controle_censura.txt
   ├── relay_status.json        (gerado automaticamente)
   ├── relay.log                (gerado automaticamente)
   ├── Relay (iniciar).bat
   ├── DOCUMENTACAO_COMPLETA.md
   ├── Script/
   │   ├── Diamante Roxo.py
   │   ├── relay.js
   │   ├── node_modules/        (criado pelo npm install)
   │   └── relatório_*.log      (gerado automaticamente)
   ```

8. Edite `Painel_de_Controle.txt` com as configurações da sua live.

9. Execute:
   ```bash
   python "Script/Diamante Roxo.py"
   ```

### 12.2. Durante a Live

O sistema roda sozinho seguindo os horários do painel.  
O usuário pode:
- Trocar cenas manualmente no OBS → o sistema redireciona automaticamente.
- Pular filmes manualmente → detectado como skip.
- Mutar o MSG_PIX → sistema pausa ducking.

### 12.3. Encerramento

O sistema encerra automaticamente ao final do fluxo (após FINAL).  
Para encerrar manualmente: feche a janela do terminal.

---

## 13. Relay (FFmpeg Relay para Kick)

### 14.1. Visão Geral

O Relay é uma camada intermediária que desacopla o OBS da instabilidade do servidor RTMPS do Kick (AWS MediaLive).  
Em vez de OBS → Kick direto, o fluxo passa por um servidor RTMP local que encaminha o stream via FFmpeg.

### 14.2. Arquitetura

```
OBS → rtmp://127.0.0.1:1936/live/stream (local)
                ↓
        node-media-server (porta 1936)
                ↓
        FFmpeg → rtmps://fa723fc1b171.global-contribute.live-video.net/app/KEY
                ↓
              Kick (AWS MediaLive)
```

### 14.3. Componentes

| Arquivo | Função |
|---|---|
| `relay.js` | Node.js: servidor RTMP local (node-media-server) + FFmpeg push |
| `Painel_de_Controle.txt` | Config: `usar_relay`, `kick_stream_key`, `kick_stream_server` |
| `Relay (iniciar).bat` | Atalho para iniciar relay manualmente (independente) |

### 14.4. Fluxo de Inicialização

1. `conectar_obs()` (agendado) → conecta OBS + **inicia relay** (node-media-server)
2. `start_sistema()` (agendado) → chama `testar_conexao_kick()` (FFmpeg dummy 0.5s)
   - Se falhar → **aborta**, nenhum `start_stream` é chamado
3. `iniciar_relay()` → sobe relay se ainda não estiver rodando
4. `client.start_stream()` → OBS envia para `127.0.0.1:1936`
5. relay.js detecta `postPublish` → inicia `FFmpeg -c copy` para o Kick
6. `esperar_relay_conectar(timeout=30)` → aguarda `relay_status.json: {connected: true}`
7. Se timeout → `client.stop_stream()` + abort
8. `iniciar_fluxo()` → cenas, mídias, etc.

### 14.5. Reconexão Automática

**relay.js:** Quando FFmpeg morre e `obsPublishing == true`, reinicia em 3s.  
**Python (monitor):** Quando relay cai durante live:

1. `pausar_filme_se_rodando()` → pausa fonte FILMES se cena = MÍDIAS
2. Mata processo relay (node-media-server + FFmpeg) → OBS entra em **Reconnecting**
3. Limpa status, espera 2s
4. Reinicia relay
5. OBS reconecta, FFmpeg reinicia via `postPublish`
6. `relay_status.json: {connected: true}` → programa retomada do filme em **5s**
7. Após 5s estável: `retomar_filme_se_pausado()` → play na fonte FILMES

### 14.6. Teste de Conexão

`testar_conexao_kick()` executa FFmpeg com entrada sintética de 0.5s para Kick:

```
ffmpeg -f lavfi -i color=c=black:s=1280x720:r=30:d=1
       -f lavfi -i anullsrc=r=48000:cl=stereo
       -c:v libx264 -preset ultrafast -t 0.5
       -f flv rtmps://server/live/KEY
```

- Exit code 0 → Kick acessível → prossegue
- Exit code ≠ 0 → aborta sistema

### 14.7. Comportamento Sem Relay

Se `usar_relay = no` no Painel de Controle:
- Nenhum componente de relay é iniciado
- `testar_conexao_kick()` não é chamado
- OBS transmite direto para o servidor configurado manualmente nas settings do OBS
- Toda lógica de relay é ignorada, sistema funciona como antes

### 14.8. Dependências

- **Node.js** para `relay.js`
- **node-media-server** (npm) — servidor RTMP local
- **FFmpeg** no PATH — push RTMPS para o Kick

### 14.9. Configuração no Painel de Controle

```
usar_relay       = yes
kick_stream_key  = sk_us-west-2_XXXXXXXXXXXXX
kick_stream_server = rtmps://fa723fc1b171.global-contribute.live-video.net/app/
```

> **Importante:** O protocolo deve ser `rtmps://` (TLS/SSL). `rtmp://` puro é rejeitado pelo servidor AWS MediaLive.

---

## 14. Regras de Desenvolvimento

1. **Explicar antes de aplicar** — você vê e entende primeiro, só aplico quando autorizar.
2. **Código em português** — comentários, logs, nomes, tudo em PT-BR.
3. **Sem emojis** — nem em prints, nem em comentários, nem em logs.
4. **Performance primeiro** — hardware limitado (I5-3470 + HD Graphics), toda decisão prioriza CPU.
5. **Honestidade** — se uma mudança não ajudar de verdade, eu falo.
6. **Documentar** — toda mudança relevante vai pra `DOCUMENTACAO_COMPLETA.md`.
7. **Comentar o código** — explicar o porquê, não o óbvio.
8. **Perguntar quando não tiver certeza** — nunca assumir.
9. **Versão baseada na data** — revisão distante da criação → número inteiro (5.0, 6.0...). Revisão próxima da anterior → número picotado (4.2, 5.1...).

---

## Histórico de Versões

| Versão | Data | Mudanças |
|---|---|---|
| 4.8 | 09/07/2026 | **Relay FFmpeg para Kick:** relay.js (node-media-server + FFmpeg push RTMPS), `testar_conexao_kick()` antes de start_stream, correção do protocolo `rtmp://` → `rtmps://`, correção do bug `start_stream()` nunca chamado, detecção de conexão `[q] to stop`, pausa automática de filme na queda do relay com retomada 5s após reconexão, sincronia OBS → "Reconnecting" via kill do node-media-server. Encerramento suave do FFmpeg (envia `q` pelo stdin). |
| 4.10 | 10/07/2026 | **Reorganização da pasta Códigos:** `TWITCH/` → `Diamante_Roxo/`, scripts espalhados agrupados em `Utilitarios/`, `Manutencao/`, `Antigos/`. Caminhos atualizados nos utilitários. |
| 4.9 | 10/07/2026 | **Modo destino no estudo:** campo `modo_destino` no Painel de Controle define se `iniciar_midias` vai para filmes ou rerun. `iniciar_midias_direto()` altera `global_modo_conteudo` + título da live (`REACT`/`RERUN`) antes da transição. |
| 4.7 | 09/07/2026 | Modo ESTUDO: `modo_conteudo = estudo` com fluxo manual + agendamento `iniciar_midias` para transição automática a FILMES/RERUN. Novas fontes EV BRADESCO e WORD_VS desligadas em `aba_midias()` e `aba_rerun()`. Agendamento condicional (`start_sistema` ignorado se modo=estudo). |
| 4.6 | 08/07/2026 | Localização dinâmica de softwares por caminhos conhecidos (substitui caminhos fixos .lnk). Migração de `os.startfile()` para `subprocess.Popen()`. Fallback seguro quando executável não encontrado. |
| 4.5 | 06/07/2026 | Revisão de data + versão. Discussão estratégica: migração definitiva pro Kick, categoria Movierooms |
| 4.4 | 04/07/2026 | Sistema de plataforma: `plataforma = twitch` inicia todos os apps, `kick` inicia só OBS + Streamer.bot |
| 4.3 | 04/07/2026 | Removido sistema de controle de prioridade dos navegadores |
| 4.2 | 03/07/2026 | Controle de prioridade dos navegadores (rebaixa Edge, Brave, WhatsApp, Spotify), polling dos loops reduzido (0.5s, 3s, 1s), polling do painel para 5s, documentação completa |
| 4.1 | 01/07/2026 | Refatoração de transições, cache de visibilidade, otimizações de performance, limpeza de comentários e emojis, cabeçalho profissional |
