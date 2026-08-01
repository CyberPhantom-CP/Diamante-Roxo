# Diamante Roxo — Jornada v1.0 → v4.13

## Origem (24/03/2026)

Dois scripts independentes: **Assistente Virtual (Twitch)** e **Esmeralda (Kick)**. Ambos com `exit()` na linha 13 — nunca rodaram de verdade. Eram esqueletos: 300 linhas, caminhos `.lnk` fixos, configuração dura no código, sem alertas, sem RERUN, sem pausa noturna.

## O despertar

O `exit()` foi removido e o script começou a funcionar. Mas era frágil:
- Mudasse o IP do PC, a conexão OBS quebrava
- IP dinâmico (`192.168.1.x`) foi substituído por `127.0.0.1` (solução definitiva)
- Caminhos `.lnk` quebravam se reinstalasse o software

## A grande fusão

Os dois scripts (Twitch + Kick) foram unificados num só: **Diamante Roxo**. Nasceu o `Painel_de_Controle.txt` — tudo configurável sem mexer no código. Plataforma vira chave: `twitch` abre todos os apps, `kick` só OBS + Streamer.bot.

## GrampeadoOBS — o sistema de alertas

Veio a complexidade: alertas com ducking de áudio, fade-in/fade-out, transições controladas, pausa automática do filme durante alerta. Uma classe EventClient inteira para monitorar volumes e cenas em tempo real.

## Censura e Tarja

Sistema dinâmico: cada filme pode ter regras de censura por timestamp, com múltiplas fontes por bloco. Lê do `controle_censura.txt` e ativa/desativa automaticamente.

## Pausa Noturna

3 camadas de proteção para não passar das 23h:
1. Oráculo: calcula se o próximo filme estoura o limite — se sim, nem engata
2. Se passou das 23h, aborta direto
3. Skip manual também respeita o horário

## RERUN

Modo retransmissão ao vivo com contagem regressiva, fontes dedicadas (RERUN + SPOTIFY), suporte a dias e horário final configurável.

## Localização Dinâmica de Software

A última grande evolução: chega de caminhos fixos. Busca automática com fallback de 3 níveis — ProgramFiles, AppData, Documents, Desktop, Downloads, C:\. Agora sobrevive a reinstalações e mudanças de pasta.

## v4.10 — Reorganização da pasta Códigos + correção RERUN (10/07/2026)

### Estrutura organizada

```
Códigos/
├── Diamante_Roxo/        (antiga TWITCH/)
├── Utilitarios/          (gerar_tempo.py, Gerar_Censuras.py)
├── Manutencao/           (Comandos.txt, manutenção Windows)
├── Antigos/              (scripts obsoletos pré-fusão)
└── Projetos_CP.code-workspace
```

Apenas dois arquivos com caminho hardcoded foram atualizados (`Gerar_Censuras.py` e `gerar_tempo.py`) — o script principal e o relay.js usam caminhos relativos dinâmicos, então funcionam com qualquer nome de pasta.

### Correção: retornar_midias durante RERUN

`auto_retorno_midias()` agora verifica `global_modo_conteudo` antes de agir. Se for RERUN, ignora — evitava tentar dar play em filme durante retransmissão.

## v4.9 — Documentação completa de dependências (10/07/2026)

Inventário completo de tudo que o sistema precisa pra funcionar do zero:

- Python + pip (4 pacotes: `schedule`, `psutil`, `pywinauto`, `obsws_python`)
- Node.js + npm (1 pacote: `node-media-server`)
- FFmpeg no PATH
- 4 softwares (OBS, Streamer.bot, Mix It Up, Chatty)
- 8 arquivos do projeto que precisam de backup
- Config do OBS (`%APPDATA%/obs-studio/`)

Cada instalação tem passo a passo com link direto no `DOCUMENTACAO_COMPLETA.md` — se formatar o PC, segue a seção 12.1 e volta ao ar.

### Encerramento suave do relay

`relay.js` agora envia `q` pelo stdin do FFmpeg no lugar de `SIGTERM` (inexistente no Windows). FFmpeg fecha a conexão RTMP limpa — sem "Protection Disconnecting" no Kick.

### Modo destino no estudo

Novo campo `modo_destino = filmes` / `rerun` no Painel de Controle. Quando `iniciar_midias` dispara em modo estudo:
1. `global_modo_conteudo` muda pro destino
2. `id_live()` atualiza o título (REACT/RERUN)
3. Pula direto pra MÍDIAS, sem ENTRADA → INÍCIO

### Imports organizados

Separados em "Biblioteca Padrão" e "Bibliotecas de Terceiros", ordem alfabética.

## v4.7 — Modo ESTUDO (09/07/2026)

Novo modo de operação: **ESTUDO**. Diferença fundamental dos anteriores:

- `modo_conteudo = estudo` muda o comportamento do agendamento:
  - `start_sistema` é ignorado — você inicia OBS e transmissão manualmente.
  - `iniciar_midias` (novo) dispara a transição de estudo para filmes/rerun no horário agendado.
- Duas novas fontes na cena MÍDIAS: **EV BRADESCO** (site do curso) e **WORD_VS** (anotações).
- Em `aba_midias()` e `aba_rerun()`, EV BRADESCO e WORD_VS são automaticamente desligadas ao entrar.
- A arquitetura agora suporta 3 fluxos: normal (entrada→início→mídias), rerun (direto), e estudo (manual→automático).

## v4.8 — Relay FFmpeg para Kick (09/07/2026)

O Kick usa AWS MediaLive como servidor de ingestão. O problema: o endpoint `live-video.net` oscila — OBS entra em loop de reconexão, stream cai, live morre.

**Solução:** um relay local. OBS nunca mais conecta direto no Kick.

```
OBS → node-media-server (127.0.0.1:1936) → FFmpeg → rtmps://Kick
```

Três componentes novos:
- `relay.js`: Node.js + node-media-server + FFmpeg. Faz tudo sozinho.
- `Relay (iniciar).bat`: atalho pra testar sem o script.
- Seção `RELAY` no `Painel_de_Controle.txt`: `usar_relay`, `kick_stream_key`, `kick_stream_server`.

### Bug crítico corrigido

O código original do `start_sistema()` tinha:

```python
if modo in ["gravar", "teste"]:
    if modo in ["gravar", "teste"]:  # ← MESMA CONDIÇÃO!
        start_record()
    else:
        start_stream()  # ← NUNCA EXECUTAVA
```

`start_stream()` era **dead code** desde o começo. O script mudava cenas mas a live nunca iniciava automático. O usuário sempre teve que apertar "Iniciar transmissão" manualmente. 4 versões e ninguém percebeu.

### RTMP vs RTMPS

Outro erro desde o início: o relay tentava `rtmp://` (porta 1935), mas o AWS MediaLive exige `rtmps://` (TLS, porta 443). OBS negociava sozinho, FFmpeg não — caía com ECONNRESET. Trocado o protocolo, conexão imediata.

### Teste de conexão pré-stream

`testar_conexao_kick()` usa FFmpeg com entrada sintética (0.5s de dummy) para verificar se o servidor Kick está acessível **antes** de qualquer `start_stream`. Se falhar, o sistema aborta — nenhuma transmissão começa sem relay confirmado.

### Sincronia OBS-Relay

Quando o relay cai durante a live:
1. Monitor detecta
2. Pausa o filme (como nos alertas)
3. Mata o node-media-server → OBS entra em **Reconnecting**
4. Reinicia o relay
5. OBS reconecta, FFmpeg sobe
6. Após 5s de estabilidade: filme retoma

### Lição

O sistema funcionava "na sorte" — o usuário sempre iniciava a transmissão manualmente porque o automático nunca funcionou. 4 versões sem ninguém notar. O relay expôs o bug porque exigiu automação completa.

## O que não mudou

- x264 ultrafast, baseline, 4000 CBR — intocável desde o começo
- 1280x720, 30 FPS
- i5-3470, HD Graphics 2500, 16GB — o hardware que dita os limites
- Código em português, sem emojis

## Números

| Métrica | v1.0 | v4.6 | v4.7 | v4.8 | v4.9 | v4.10 |
|---------|------|------|------|------|------|-------|
| Linhas | 317 | ~1542 | ~1562 | ~1887 | ~1900 | ~1903 |
| Funções | 15 | ~45 | ~47 | ~55 | ~56 | ~56 |
| Classes | 0 | 1 (GrampeadoOBS) | 1 | 1 | 1 | 1 |
| Arquivos de config | 0 | 3 | 3 | 3 | 3 | 3 |
| Modos de operação | 1 | 3 | 4 (+ estudo) | 4 | 4 | 4 |
| Plataformas | 1 | 2 | 2 | 2 | 2 | 2 |
| Fontes gerenciadas | 0 | 12 | 14 | 14 | 14 | 14 |
| Resultado | Travado com `exit()` | 49 frames perdidos | — | Relay + RTMPS | Docs completas | Pastas organizadas |

## v4.11 — Correções relay + fluxo antecipado (14/07/2026)

### Bugfix: `h264_metadata` com parâmetro inválido

O bitstream filter usava `num_units_in_tick=1001:time_scale=30000`, mas o FFmpeg 8.1 não reconhece essas opções — usa `tick_rate` (time_scale/num_units_in_tick). O relay crashava instantaneamente com EINVAL.

**Corrigido:** `tick_rate=30` (30fps exato no VUI).

### Fluxo antecipado

Antes: `start_sistema()` esperava o relay conectar (até 30s) para só então iniciar as cenas — a ENTRADA de 9s começava atrasada.

**Agora:** `iniciar_fluxo()` roda imediatamente. O relay conecta em paralelo durante os 9s da ENTRADA. O INÍCIO de 07min05 não atrasa mais.

### Monitor de stream nativo (OBS direto)

Quando `usar_relay = nao`, o pause/resume do filme durante quedas era perdido. Agora o `GrampeadoOBS` escuta `OutputStateChanged` do WebSocket:

- **STOPPED** inesperado (sem `_stopping_stream`) → `pausar_filme_se_rodando()`
- **STARTED** → `retomar_filme_se_pausado()`

Flag `_stopping_stream` evita pause falso em `stop_stream()` intencional.

### Observação

RTMPS cai após ~34 min (servidor Kick fecha TLS). O relay faz fallback automático para SRT, mas a Kick cria uma live nova no processo. Se o SRT se mostrar estável, pode-se trocar a ordem (SRT primário, RTMPS fallback).

## v4.12 — Monitor de saúde da stream (15/07/2026)

### Problema

A sessão de 15/07 rodou 10.5h sem splits detectados pelo `OutputStateChanged`. Mas o OBS tem auto-reconnect: quando perde conexão, entra em **Reconnecting** (não STOPPED) e tenta reconectar. Se reconectar rápido (segundos), o evento nunca dispara e o monitor nativo (v4.11) não registra nada. O log fica limpo mas o stream splitou no Kick.

### Solução — `monitorar_saude_stream()` (Diamante Roxo.py:1142)

Thread daemon com **conexão WebSocket própria** (`ReqClient` separado) — zero interferência com o `client` principal:

- Polla `GetStreamStatus` a cada **5 minutos**
- Loga três campos críticos:
  - **`outputActive`** — se ficar False, o stream morreu (mesmo que OBS já tenha reconectado)
  - **`outputReconnecting`** — True se OBS está no estado intermediário de reconexão
  - **`outputDuration`** — tempo acumulado de stream em segundos
- **Detecção de split automática**: compara `duration` com o valor anterior. Se caiu (mesmo que OBS já tenha reconectado), loga `<<< SPLIT DETECTADO (perdeu Xs desde ultima checagem)` — impossível de ignorar no log
- Conexão própria evita colisão com `aba_geral` ou outros comandos
- `disconnect()` explícito ao sair para não vazar socket
- Daemon: morto automaticamente quando o processo principal encerra

### IPv4-only já configurado

O perfil OBS `KICK/basic.ini` já estava em `IPFamily=IPv4` — uma variável a menos para investigar.

## v4.13 — Relay v2: SRT primário, HTTP health, retry inteligente (15/07/2026)

### Problema

O relay v1 tinha:
- RTMPS como primário (cai ~34 min por timeout TLS do AWS IVS)
- Fallback SRT só tentava uma vez, sem ciclo de retorno
- Retry fixo (5/10/20/30s), sem jitter
- Detecção de conexão via arquivo JSON (`relay_status.json`) com race condition
- Nenhuma métrica de saúde (bitrate, fps, reconexões)
- Parse de stderr básico (só detectava `[q] to stop`)

### Solução — `relay.js` v2 + `Diamante Roxo.py` v4.13

#### relay.js v2 (reescrito de 243 → ~300 linhas)

**Arquitetura nova:**

1. **SRT como protocolo primário** — SRT tem ARQ (correção de erro embutida), buffer de latência configurável, reconexão transparente. RTMPS vira fallback.
2. **Retry inteligente com jitter** — exponential backoff: 1s, 2s, 4s, 8s, 15s, 20s, 25s, 30s (cap). ±250ms aleatório evita thundering herd.
3. **Ciclo SRT→RTMPS→SRT**: se SRT falha → RTMPS imediato (1s). A cada 3 falhas do RTMPS, tenta SRT novamente. Reset na primeira conexão bem-sucedida.
4. **HTTP health endpoint** (`http://127.0.0.1:1937/health`): JSON com connected, protocol, bitrate_kbps, fps, uptime_seconds, reconnects, retryCount, lastError. Substitui JSON file como fonte principal (fallback mantido).
5. **Parse detalhado do stderr**: extrai bitrate, fps, frames totais, speed em tempo real. Detecta erros específicos (TLS_ERROR, SRT_ERROR, CONNECTION_REFUSED, TIMEOUT, etc).
6. **Watchdog de dados**: monitora se FFmpeg está produzindo output. Se 15s sem dados com OBS publicando, loga aviso.
7. **NMS config melhorada**: `chunk_size: 8192`, `ping_timeout: 10`.

#### Python v4.13 — Monitor via HTTP

1. `obter_status_relay()` — tenta HTTP health endpoint primeiro (`:1937/health`, timeout 2s). Se falhar, lê JSON file (backward compat).
2. `esperar_relay_conectar()` — usa obter_status_relay(), mostra protocolo ativo.
3. `_log_relay_stats()` — log periódico a cada 60s: protocolo, bitrate, fps, uptime, reconexões.
4. `monitorar_relay_loop()` — agora mostra stats detalhados nas transições de estado.

### Números v4.13

| Métrica | v4.12 | v4.13 |
|---------|-------|-------|
| Linhas Python | ~2022 | ~2060 |
| relay.js | 243 | ~300 |
| Funções relay | 4 | ~15 |
| HTTP endpoints | 0 | 2 (`/health`, `/stats`) |
| Protocolos | RTMPS→SRT | SRT→RTMPS→SRT |
| Retry | 4 delays fixos | 8 delays + jitter ±250ms |
| Monitoramento | JSON file only | HTTP + JSON fallback |
