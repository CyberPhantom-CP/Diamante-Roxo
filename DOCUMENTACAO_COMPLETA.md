# Diamante Roxo v5.1 — Documentação Completa

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

**Nome:** Diamante Roxo v5.1  
**Autor:** CyberPhantom (C.P.)  
**Função:** Automatizar transmissões ao vivo gerenciando OBS Studio, Streamer.bot, Mix It Up, Chatty e Kickerino.

O sistema opera em três modos principais:
- **FILMES:** Reprodução de mídia com sistema de censura por tempo e saltos pós-créditos.
- **RERUN:** Retransmissão ao vivo com contagem regressiva e fontes dinâmicas.
- **ESTUDO:** Fluxo híbrido — transmissão manual com estudo, transição automática para FILMES/RERUN via `iniciar_midias`.

Suporta duas plataformas:
- **Twitch:** todos os apps são iniciados (Mix It Up, Chatty, Streamer.bot, OBS).
- **Kick:** Streamer.bot, Kickerino e OBS são iniciados.

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
              cena MÍDIAS com [SITE] + [ANOTACOES]
                    │
                    ▼ (agendado: iniciar_midias)
              iniciar_midias_direto()
                    │
                    ▼
              Desliga [SITE] + [ANOTACOES]
              Liga FILMES/GIF/SESSÃO ID (ou RERUN)
                    │
              ┌─────┴─────┐
              ▼           ▼
          aba_midias()  aba_rerun()
          (FILMES)      (RERUN)
```

Durante todo o ciclo, o **GrampeadoOBS** (EventClient) escuta eventos do OBS em segundo plano:
- **on_current_program_scene_changed:** detecta troca manual de cena.
- **on_input_volume_meters:** monitora volume do [FONTE_ALERTA] para detectar alertas.
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
| `[OBS_SCHED]` | Inicia OBS Studio | Ambas |
| `chatty` | Inicia Chatty | Só Twitch |
| `kickerino` | Inicia Kickerino (cliente de chat da Kick) | Só Kick |
| `minimizar_janelas` | Minimiza todos os apps | - |
| `conectar_obs` | Conecta ao OBS WebSocket | - |
| `start_sistema` | Inicia transmissão/gravação | - |
| `retornar_midias` | Retorna de PAUSA para MÍDIAS | - |
| `iniciar_midias` | Dispara transição de estudo (só modo=estudo) | - |
| `oraculo_ativado` | Habilita/desabilita pausa noturna 23h-06h | - |
| `pausa_apos_filmes` | Pausa após N filmes (0 = desativado) | - |
| `pausa_retorno` | Horário de retorno da pausa por quantidade | - |
| `oraculo_retorno` | Horário de retorno da pausa noturna | - |

O scheduler verifica o arquivo a cada 5 segundos. Se houver alteração, recarrega tudo.

> **Nota:** desde a v5.0, os campos de horário em branco no painel **não são agendados** (antes um campo vazio virava `00:00:00` e agendava a ação para a meia-noite). Um horário só é agendado se o campo estiver preenchido.

### 3.3. Cenas (Sequência)

```
ENTRADA (9s) → INÍCIO (7min05s) → MÍDIAS (loop filmes) → PAUSA (noturna ou por quantidade, opcional)
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
  - Verifica **pausa por quantidade** (`pausa_apos_filmes`) — detecta 30s antes do fim e pausa após o enésimo filme.
- Ao final de todos os filmes, avança para RAIDA.

**Pausa por Quantidade de Filmes:**
Quando `pausa_apos_filmes > 0` no painel, o sistema pausa a reprodução depois que determinada quantidade de filmes termina:
- Detecta **30s antes do fim** do filme de índice igual a `pausa_apos_filmes` (mesma antecipação do oráculo).
- Grava a posição atual (`midia_decorrido_global`) para retomada futura.
- Transita para a cena **PAUSA** com modo `quantidade` (chama `aba_pausa("quantidade")`).
- Retoma automaticamente no horário de `pausa_retorno`, usando `set_media_input_cursor` para voltar à posição salva antes do PLAY (evita recomeçar do início).

**Pausa Oráculo vs. Pausa por Quantidade:**
São dois retornos independentes, configurados separadamente no painel:

| Config | Modo de pausa | Onde é definido o retorno |
|---|---|---|
| `oraculo_ativado = yes` | Pausa noturna (23h-06h) | `oraculo_retorno` |
| `pausa_apos_filmes > 0` | Pausa por quantidade | `pausa_retorno` |

O oráculo gera `pausa_oraculo` (barrou o próximo filme no minuto 1) ou `pausa_horario` (já passou das 23h na reta final). A pausa por quantidade gera `pausa_quantidade`. Cada um tem seu próprio horário de retorno e sua própria função de retomada (`oraculo_retorno` / `pausa_retorno`), eliminando a antiga confusão entre os dois fluxos.

**Controle de visibilidade das fontes na cena MÍDIAS:**

| Ligadas | Desligadas |
|---|---|---|
| GIF | WEBCAM |
| STREAMER OFF | STREAMER ON |
| FILMES | RERUN |
| SESSÃO ID | SPOTIFY |
|  | CENSURA |
|  | TARJA |
|  | [SITE] |
|  | [ANOTACOES] |

### 4.2. Modo RERUN

Controlado por `modo_conteudo = rerun` no painel.

- Apenas fontes RERUN, SPOTIFY e STREAMER OFF ficam visíveis. [SITE] e [ANOTACOES] são desligadas.
- Exibe contagem regressiva ao vivo até o horário configurado em `rerun_horario_final`.
- Detecta alterações em tempo real nos parâmetros do painel (dias, horário).
- Ao finalizar, redireciona conforme `saida_rerun`:
  - `raid` → aba_raid()
  - `reset` → resetar_fluxo() (recomeça do início)
  - `final` → aba_final()

### 4.3. Modo ESTUDO

Controlado por `modo_conteudo = estudo` no painel.

- Fluxo híbrido para dias de estudo presencial:
  - Você abre OBS + transmissão manualmente (cena MÍDIAS com fontes [SITE] e [ANOTACOES] visíveis).
  - `conectar_obs` conecta o WebSocket no horário agendado.
  - `start_sistema` é **ignorado** — não força ENTRADA/INÍCIO.
  - `iniciar_midias` (agendado separadamente) dispara a transição:
    1. Garante que a cena MÍDIAS está ativa.
    2. Desliga [SITE] e [ANOTACOES].
    3. Liga FILMES + GIF + SESSÃO ID (ou RERUN + SPOTIFY).
    4. Inicia o loop normal de filmes/rerun.
- Em dias sem estudo, basta mudar para `modo_conteudo = filmes` ou `rerun` — `iniciar_midias` é ignorado, `start_sistema` funciona normalmente.

---

## 5. Sistema de Alertas

### 5.1. Detecção

A classe `GrampeadoOBS` monitora o volume de `[FONTE_ALERTA]` (definido em `fontes_alertas`).
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

A fonte `[FONTE_ALERTA]` (definida em `fontes_alertas`) é automaticamente excluída do ducking mesmo se listada em `fontes_por_cena`.

### 5.3. Timer de Retorno

Quando o volume do `[FONTE_ALERTA]` volta ao normal:
- Um timer de **3 segundos** é iniciado.
- Se outro alerta chegar antes do timer finalizar, o timer é **cancelado e reiniciado**.
- Se o timer completar 3 segundos, o sistema restaura todos os volumes com **fade-in de 2 segundos** em 8 passos.

### 5.4. Tratamento de Mixer Mutado

Se o usuário mutar o mixer do `[FONTE_ALERTA]` no OBS:
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
oraculo_ativado       = yes / nao        # Habilita pausa noturna 23h-06h (yes/sim/true)
pausa_apos_filmes     = 0                # Pausa após N filmes (0 = desativado)
pausa_retorno         = HH:MM:SS         # Retorno da pausa por quantidade
oraculo_retorno       = HH:MM:SS         # Retorno da pausa noturna
[OBS_HOST]              = [HOST]        # IP do OBS
[OBS_PORT]              = [PORTA]             # Porta WebSocket
[OBS_SENHA]          = [SENHA]             # Senha WebSocket
mixitup               = HH:MM:SS         # Horário para iniciar
streamerbot           = HH:MM:SS
[OBS_SCHED]           = HH:MM:SS
chatty                = HH:MM:SS
kickerino              = HH:MM:SS
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
| `start_[OBS_SCHED]()` | Inicia OBS Studio (localização dinâmica + subprocess.Popen) |
| `start_chatty()` | Inicia Chatty (localização dinâmica + subprocess.Popen) |
| `start_kickerino()` | Inicia Kickerino (localização dinâmica + subprocess.Popen) |
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
| `aba_pausa(modo)` | Pausa até troca manual — `modo` define o retorno: `"quantidade"` (usa `pausa_retorno`) ou default/`"oraculo"` (usa `oraculo_retorno`). Na retomada, refaz o seek para a posição salva antes do PLAY |
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
| `stop_sistema()` | Para stream/record + encerra (usa `_travar_painel_seguranca`) |
| `verificar_agendamento()` | Monitora Painel_de_Controle.txt + agenda tarefas (condiciona `iniciar_midias` / `start_sistema` conforme `modo_conteudo`) |
| `auto_retorno_midias()` | Retorno automático da PAUSA |
| `_travar_painel_seguranca()` | Reescreve `executar_sistema = no` + `pausa_apos_filmes = 0` no painel (compartilhada entre `stop_sistema` e `_ao_parar`) |

---

## 10. GrampeadoOBS (Classe Principal)

Subclasse de `EventClient` (obsws_python).  
Gerencia toda a resposta a eventos do OBS em tempo real.

### 10.1. Atributos

| Atributo | Tipo | Descrição |
|---|---|---|
| `fontes_alertas` | list | Fontes que disparam alerta (padrão: `["[FONTE_ALERTA]"]`) |
| `fontes_por_cena` | dict | Mapeamento cena → fontes para ducking |
| `cena_atual` | str | Cena atual no OBS |
| `resgate_em_andamento` | bool | True durante alerta ativo |
| `timer_retorno` | Timer | Timer de 3s para finalizar resgate |
| `volumes_originais` | dict | Volumes salvos antes do ducking (cofre) |
| `transicao` | dict | Estado da transição atual (se houver alerta) |
| `mixer_mutado` | bool | True se [FONTE_ALERTA] está mutado |
| `_midia_pausada_pelo_alerta` | bool | True se FILMES foi pausado pelo alerta |
| `_vol_lock` | threading.Lock | Protege o acesso a `volumes_originais` (thread-safety) |

> **Nota (v5.0):** `volumes_originais` (o "cofre") é lido/escrito tanto pela thread de eventos do OBS quanto por threads de `threading.Timer`. O lock `_vol_lock` protege esse dicionário — antes podia perder ou duplicar uma entrada se as duas threads caíssem ao mesmo tempo. `finalizar_resgate_com_seguranca()` agora captura e limpa o cofre numa única operação protegida por lock.

### 10.2. Event Handlers

| Método | Evento OBS | Ação |
|---|---|---|
| `on_current_program_scene_changed` | Cena trocada | Gerencia transição com alerta |
| `on_input_volume_meters` | Volume do áudio mudou | Detecta alerta e faz ducking |
| `on_input_mute_state_changed` | Estado de mute | Trata mutar/desmutar do [FONTE_ALERTA] |

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

Python 3.14 instalado e no PATH (testado nesta versão; códigos 3.10+ funcionam).

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

### 11.3. Softwares Gerenciados (iniciados pelo script)

| Software | Executável | Função |
|---|---|---|
| **OBS Studio** | `[OBS_EXE]` | Transmissão, gravação, cenas, fontes |
| **Streamer.bot** | `Streamer.bot.exe` | Eventos, comandos e alertas da live |
| **Mix It Up** | `MixItUp.exe` | Chat, interatividade e comandos (Twitch) |
| **Chatty** | `Chatty.exe` | Cliente de chat com moderação (Twitch) |
| **Kickerino** | `Kickerino.exe` | Cliente de chat da Kick (equivalente ao Chatty). Instala em `Documents/Kickerino_<versão>_Windows/` |

### 11.4. Arquivos do Projeto (devem estar salvos)

| Arquivo | Pasta | Função |
|---|---|---|
| `Diamante Roxo.py` | `TWITCH/Script/` | Script principal |
| `Painel_de_Controle.txt` | `TWITCH/` | Configuração principal |
| `tempo_duracao.txt` | `TWITCH/` | Durações e saltos dos filmes |
| `controle_censura.txt` | `TWITCH/` | Regras de censura por filme |
| `DOCUMENTACAO_COMPLETA.md` | `TWITCH/` | Documentação completa |
| `JORNADA_DIAMANTE_ROXO.md` | `TWITCH/` | Histórico de versões |

### 11.5. Arquivos Gerados em Execução

| Arquivo | Pasta | Conteúdo |
|---|---|---|
| `relatório_<data>.log` | `TWITCH/Script/` | Log da sessão |

### 11.6. Configuração OBS

| Arquivo | Caminho | Observação |
|---|---|---|
| `[PERFIL]` | `[PASTA_OBS]/[PERFIL_DIR]/` | Perfil 1280x720, 30 FPS, CBR 4000 |
| `[ENCODER]` | `[PASTA_OBS]/[PERFIL_DIR]/` | x264 ultrafast, baseline |
| `[GLOBAL]` | `[PASTA_OBS]/` | BrowserHWAccel=true, ProcessPriority=High |
| `[CENARIOS]` | `[PASTA_OBS]/[CENAS_DIR]/` | Cena principal com 15 sources |

> **Dica:** Backupeie a pasta `[PASTA_OBS]/` inteira. Contém perfil, cenas, fontes, configurações de áudio e encoding.

---

## 12. Como Usar

### 12.1. Primeira Configuração (do zero)

#### 12.1.1. Instalar Python

1. Acesse https://www.python.org/downloads/
2. Baixe a versão mais recente (3.12+ ou 3.13+; o projeto foi testado em 3.14)
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

#### 12.1.3. Configure o OBS Studio

- Ative o WebSocket em Ferramentas → WebSocket Server Settings.
- Porta padrão: [PORTA] (ou configure no Painel de Controle).
- Senha opcional.
- Configure a transmissão da Kick diretamente nas settings do OBS (Ferramentas → Configurações → Transmissão).
  O sistema **não** gerencia relay — o OBS transmite direto para a Kick.

#### 12.1.4. Coloque todos os arquivos do projeto na estrutura correta

```
TWITCH/
├── Painel_de_Controle.txt
├── tempo_duracao.txt
├── controle_censura.txt
├── DOCUMENTACAO_COMPLETA.md
├── Script/
│   └── Diamante Roxo.py
│   └── relatório_*.log      (gerado automaticamente)
```

#### 12.1.5. Edite `Painel_de_Controle.txt` com as configurações da sua live.

#### 12.1.6. Execute

```bash
python "Script/Diamante Roxo.py"
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
- Mutar o [FONTE_ALERTA] → sistema pausa ducking.

### 12.3. Encerramento

O sistema encerra automaticamente ao final do fluxo (após FINAL).  
Para encerrar manualmente: feche a janela do terminal.

---

## 13. Transmissão Direta para a Kick (sem Relay)

### 13.1. Visão Geral

Desde a v5.0, o **relay FFmpeg foi removido**. O OBS transmite **diretamente** para a Kick, sem camada intermediária. O fluxo de relay de versões anteriores ([RELAY_JS], [NODE_MEDIA], FFmpeg push RTMPS) **não existe mais** no código atual.

### 13.2. Arquitetura

```
OBS Studio → Kick (configurado diretamente nas settings de transmissão do OBS)
```

- A conexão com a Kick é configurada manualmente no OBS (Ferramentas → Configurações → Transmissão).
- O sistema não inicia nem gerencia nenhum processo de relay.
- O parâmetro `usar_relay` e as chaves `kick_stream_key` / `kick_stream_server` **não são mais lidos** pelo código.

### 13.3. Por que foi removido

As versões 4.8 a 4.13 usavam um relay local ([NODE_MEDIA] + FFmpeg) para contornar quedas do servidor RTMPS do Kick. Após testes de estabilidade, a transmissão direta se mostrou suficiente e estável, então o relay virou complexidade desnecessária (processos extras, arquivos `[RELAY_JS]`/`[RELAY_STATUS]`/`[RELAY_LOG]`, dependências de Node.js/FFmpeg). A v5.0 simplificou para OBS → Kick direto.

### 13.4. Impacto nas dependências

Com a remoção do relay:
- **Node.js** já não é necessário (não há mais `[RELAY_JS]`).
- **FFmpeg** já não é necessário (não há mais push RTMPS nem `testar_conexao_kick()`).
- **[NODE_MEDIA]** (npm) já não é necessário.
- A pasta `Script` não contém mais `[RELAY_JS]` nem `node_modules/`.
- Os arquivos `[RELAY_LOG]` e `[RELAY_STATUS]` não são mais gerados.

> **Nota histórica:** as versões 4.8–4.13 documentaram o relay na JORNADA_DIAMANTE_ROXO.md e no histórico abaixo. Eles permanecem como registro do passado; a v5.0 não usa mais nenhum deles.

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
| 5.1 | 01/10/2026 | **Kickerino (cliente de chat da Kick):** novo app gerenciado, exclusivo da plataforma Kick (simétrico ao Chatty, que é exclusivo do Twitch). `start_kickerino()` + agendamento `kickerino` no painel sob o gate `plataforma == kick` + minimização de janela. `localizar_software()` agora aceita wildcard em qualquer trecho do path (necessário porque a pasta do app carrega a versão no nome, ex.: `Kickerino_1.43_Windows`, então um path fixo quebraria a cada atualização). Correção de bug em `fontes_por_cena["PAUSA"]`, que estava como `["SPOTIFY, MÚSICAS"]` (uma string com vírgula) e portanto nunca aplicava ducking — agora é `["SPOTIFY", "MÚSICAS"]`. `aba_midias()` desliga MÚSICAS e `aba_rerun()` liga MÚSICAS. |
| 5.0 | 31/08/2026 | **Pausa por quantidade + oráculo isolado + correções de robustez:** pausa após N filmes (`pausa_apos_filmes`/`pausa_retorno`, `aba_pausa("quantidade")` com retomada via seek na posição salva), retornos independentes oráculo/quantidade (`oraculo_retorno`/`pausa_retorno`), `_vol_lock` para thread-safety do cofre de volumes, `_travar_painel_seguranca()` compartilhada entre `stop_sistema`/`_ao_parar` (correção que procurava pela chave e não pelo texto exato), `finally` garante `_stopping_stream = False` mesmo se `stop_stream/stop_record` falhar, `except Exception` em vez de `except:` em todos os blocos, agendamento ignora campos de horário em branco (não mais `00:00:00` à meia-noite), leitura do painel com `with open()` fechando o arquivo, **remoção do relay FFmpeg** (OBS transmite direto para a Kick; Relay, `usar_relay`, `kick_stream_key`/`kick_stream_server`, `testar_conexao_kick()`, `[RELAY_JS]` e as dependências Node.js/FFmpeg deixam de existir). |
| 4.13 | 15/07/2026 | Relay v2: SRT primário, HTTP health endpoint (`/health`, `/stats`), retry inteligente com jitter (8 delays + ±250ms), ciclo SRT→RTMPS→SRT, parse detalhado do stderr (bitrate/fps), watchdog de dados, monitor via HTTP no Python. |
| 4.12 | 15/07/2026 | **Monitor de saúde da stream:** thread daemon `monitorar_saude_stream()` com conexão WebSocket própria polla `GetStreamStatus` a cada 5min e detecta splits mesmo com auto-reconnect do OBS. |
| 4.11 | 14/07/2026 | Correções relay: `h264_metadata` `tick_rate=30` (FFmpeg 8.1), fluxo antecipado (`iniciar_fluxo()` roda imediato, relay conecta em paralelo), monitor de stream nativo via `OutputStateChanged` com flag `_stopping_stream`. |
| 4.8 | 09/07/2026 | **Relay FFmpeg para Kick:** [RELAY_JS] ([NODE_MEDIA] + FFmpeg push RTMPS), `testar_conexao_kick()` antes de start_stream, correção do protocolo `rtmp://` → `rtmps://`, correção do bug `start_stream()` nunca chamado, detecção de conexão `[q] to stop`, pausa automática de filme na queda do relay com retomada 5s após reconexão, sincronia OBS → "Reconnecting" via kill do [NODE_MEDIA]. Encerramento suave do FFmpeg (envia `q` pelo stdin). |
| 4.10 | 10/07/2026 | **Reorganização da pasta Códigos:** `TWITCH/` → `Diamante_Roxo/`, scripts espalhados agrupados em `Utilitarios/`, `Manutencao/`, `Antigos/`. Caminhos atualizados nos utilitários. |
| 4.9 | 10/07/2026 | **Modo destino no estudo:** campo `modo_destino` no Painel de Controle define se `iniciar_midias` vai para filmes ou rerun. `iniciar_midias_direto()` altera `global_modo_conteudo` + título da live (`REACT`/`RERUN`) antes da transição. |
| 4.7 | 09/07/2026 | Modo ESTUDO: `modo_conteudo = estudo` com fluxo manual + agendamento `iniciar_midias` para transição automática a FILMES/RERUN. Novas fontes [SITE] e [ANOTACOES] desligadas em `aba_midias()` e `aba_rerun()`. Agendamento condicional (`start_sistema` ignorado se modo=estudo). |
| 4.6 | 08/07/2026 | Localização dinâmica de softwares por caminhos conhecidos (substitui caminhos fixos .lnk). Migração de `os.startfile()` para `subprocess.Popen()`. Fallback seguro quando executável não encontrado. |
| 4.5 | 06/07/2026 | Revisão de data + versão. Discussão estratégica: migração definitiva pro Kick, categoria Movierooms |
| 4.4 | 04/07/2026 | Sistema de plataforma: `plataforma = twitch` inicia todos os apps, `kick` inicia só OBS + Streamer.bot |
| 4.3 | 04/07/2026 | Removido sistema de controle de prioridade dos navegadores |
| 4.2 | 03/07/2026 | Controle de prioridade dos navegadores (rebaixa Edge, Brave, WhatsApp, Spotify), polling dos loops reduzido (0.5s, 3s, 1s), polling do painel para 5s, documentação completa |
| 4.1 | 01/07/2026 | Refatoração de transições, cache de visibilidade, otimizações de performance, limpeza de comentários e emojis, cabeçalho profissional |
