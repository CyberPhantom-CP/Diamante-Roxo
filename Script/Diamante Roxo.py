# ====================================================================
# ====================================================================
# Diamante Roxo v6.0
# ====================================================================
# Sistema de automação para transmissão ao vivo
# Gerencia cenas, áudio, alertas e transições no OBS Studio
# ====================================================================
# Aplicativos gerenciados:
#   - OBS Studio       Transmissão e gravação de áudio/vídeo
#   - Streamer.bot     Automação de eventos, comandos e alertas
#   - Mix It Up        Chat, comandos e interatividade
#   - Chatty           Cliente de chat com moderação
# ====================================================================
# Plataformas:
#   - Twitch  Todos os apps (Mix It Up, Chatty, Streamer.bot, OBS)
#   - Kick    Streamer.bot e OBS
# Modos de operação:
#   - FILMES  Reprodução de mídia com censura por tempo e saltos
#   - RERUN   Retransmissão ao vivo com contagem regressiva
#   - ESTUDO  Acionamento direto de MÍDIAS sem passa pela cena INÍCIO
# ====================================================================
# Configuração via Painel_de_Controle.txt (horários, modos, acesso OBS)
# ====================================================================
# Autor   : CyberPhantom (C.P.)
# Criado  : 24/03/2026
# Revisão : 07/11/2026
# ====================================================================

# 1) Importação de Módulos e Configuração Inicial.

print("Carregando o Sistema...")

# === Biblioteca Padrão ===
import atexit
import glob
import importlib
import math
import os
import signal
import subprocess
import sys
import threading
import time

# === Bibliotecas de Terceiros ===
import psutil
import schedule
from datetime import datetime, timedelta
from obsws_python import ReqClient, EventClient, Subs
from pywinauto import Desktop


# === Forçar Prioridade Normal no Windows ===
try:
    p = psutil.Process(os.getpid())
    # Prioridade NORMAL (padrão do Windows) para evitar starving de outros processos
    p.nice(psutil.NORMAL_PRIORITY_CLASS)
    print("Prioridade do sistema ajustada para: (PADRÃO 'NORMAL')")
except Exception as e:
    print(f"Não foi possível ajustar a prioridade: {e}")

# === CAMINHOS DINÂMICOS ===
# O script está em 'Diamante_Roxo/Script/'. Sobe um nível para 'Diamante_Roxo/' onde ficam os .txt de config.
if getattr(sys, 'frozen', False):
    pasta_sistema = os.path.dirname(sys.executable)  # Pasta 'Script' (onde está o .exe)
else:
    pasta_sistema = os.path.dirname(os.path.abspath(__file__))  # Pasta 'Script' (onde está o .py)

# Sobe um nível: de 'Diamante_Roxo/Script/' para 'Diamante_Roxo/', base para todos os arquivos do sistema
diretorio_base = os.path.dirname(pasta_sistema)

# === LOG DO SISTEMA (Fica escondido na subpasta junto com o script) ===
dia_da_sessao = time.strftime("%Y-%m-%d")
nome_ficheiro = f"relatório_{dia_da_sessao}.log"
caminho_log   = os.path.join(pasta_sistema, nome_ficheiro)

try:
    _log_handle = open(caminho_log, "a", encoding="utf-8")
except Exception:
    _log_handle = None
_log_lock = threading.Lock()
_notif_lock = threading.Lock()
_cena_lock = threading.Lock()
_toast_slots = [None, None]
_toast_ptr = 0
_toast_limpeza_feita = False
_contagem_ativa = False
_cena_pendente_log = None

def _consumir_cena_pendente(esperada=None):
    """Consome atômicamente o 'Cena trocada' pendente (evita log duplo entre threads)."""
    global _cena_pendente_log
    with _cena_lock:
        if _cena_pendente_log is None:
            return None
        if esperada is not None and _cena_pendente_log != esperada:
            return None
        valor = _cena_pendente_log
        _cena_pendente_log = None
        return valor

def log(msg, toast=False):
    global _contagem_ativa
    horario = time.strftime("%H:%M:%S")
    if _contagem_ativa:
        print(f"\r{' ' * 100}\r{horario} - {msg}", flush=True)
        _contagem_ativa = False
    else:
        print(f"{horario} - {msg}", flush=True)

    if _log_handle is not None:
        try:
            with _log_lock:
                horario_full = time.strftime("%Y-%m-%d %H-%M-%S")
                _log_handle.write(f"{horario_full} - INFO - {msg}\n")
                _log_handle.flush()
        except Exception as e:
            print(f"{time.strftime('%H:%M:%S')} - Erro ao gravar no log da sessão: {e}", flush=True)

    # Só notifica quando toast=True (pontos importantes). A contagem usa print direto, nunca entra aqui.
    if not toast:
        return
    try:
        _notifica = globals().get("notificacao")
        if _notifica is not None:
            _notifica("Diamante Roxo", f"{horario} - {msg}")
    except Exception:
        pass

def _fmt_hms(segundos):
    try:
        total = max(0, int(segundos))
        h, resto = divmod(total, 3600)
        m, s = divmod(resto, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
    except Exception:
        return "00:00:00"

def notificacao(titulo, mensagem):
    """Mostra toast v5 com 2 slots (sem duplicar), BurntToast -> plyer -> stdlib. Sem win10toast (Py3.14). Nunca quebra o script."""
    try:
        def _enviar():
            global _toast_slots, _toast_ptr, _toast_limpeza_feita
            # 1) Windows: BurntToast 2 slots (fica na Central no Win10/11)
            if sys.platform.startswith("win"):
                try:
                    # Chave de duplicacao = frase sem o "HH:MM:SS - " inicial
                    _msg_raw = str(mensagem)
                    _chave = _msg_raw
                    if len(_msg_raw) >= 11 and _msg_raw[2] == ":" and _msg_raw[5] == ":" and _msg_raw[8:11] == " - ":
                        _chave = _msg_raw[11:]
                    else:
                        _chave = _msg_raw.split(" - ", 1)[-1]
                    t = str(titulo).replace("\r", " ").replace("\n", " ").replace("'", "''").replace("$", "`$")
                    m = str(mensagem).replace("\r", " ").replace("\n", " ").replace("'", "''").replace("$", "`$")
                    with _notif_lock:
                        # Limpeza unica do slot antigo de 1 ID
                        if not _toast_limpeza_feita:
                            try:
                                subprocess.run(
                                    ["pwsh", "-NoProfile", "-WindowStyle", "Hidden", "-Command", "try { Remove-BTNotification -Id 'Diamante Roxo' -ErrorAction SilentlyContinue } catch {}"],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    timeout=10, check=False,
                                    creationflags=subprocess.CREATE_NO_WINDOW,
                                )
                            except Exception:
                                pass
                            _toast_limpeza_feita = True
                        # Escolha do slot: duplica -> reutiliza; vazio -> preenche; cheio -> substitui a mais antiga
                        if _toast_slots[0] == _chave:
                            _idx = 0
                        elif _toast_slots[1] == _chave:
                            _idx = 1
                        elif _toast_slots[0] is None:
                            _idx = 0
                        elif _toast_slots[1] is None:
                            _idx = 1
                        else:
                            _idx = _toast_ptr
                            _toast_ptr = 1 - _toast_ptr
                        _toast_slots[_idx] = _chave
                        _uid = f"Diamante Roxo {_idx + 1}"
                        bt = f"New-BurntToastNotification -Text '{t}','{m}'"
                        # 2 slots na Central, expira em 5 min cada (sem acumular)
                        bt += f" -UniqueIdentifier '{_uid}' -ExpirationTime (Get-Date).AddMinutes(5)"
                        # Usa o logo do Diamante Roxo (limpo, sem fundo de papel)
                        try:
                            _logo = os.path.join(diretorio_base, "logo.png")
                            if not os.path.exists(_logo):
                                _logo = os.path.join(os.path.dirname(sys.executable), "DLLs", "py.ico")
                            if os.path.exists(_logo):
                                bt += f" -AppLogo '{_logo}'"
                        except Exception:
                            pass
                        r = subprocess.run(
                            ["pwsh", "-NoProfile", "-WindowStyle", "Hidden", "-Command", bt],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            timeout=10, check=False,
                            creationflags=subprocess.CREATE_NO_WINDOW,
                        )
                    if r.returncode == 0:
                        return
                except Exception:
                    pass
            # 2) Híbrido: tenta plyer via import dinâmico (sem alerta no Pylance)
            try:
                mod = importlib.import_module("plyer.notification")
                mod.notify(title=str(titulo), message=str(mensagem), app_name="Diamante Roxo", timeout=4)
                return
            except Exception:
                pass
            # 3) Fallback stdlib por SO (Windows PowerShell / Linux notify-send / macOS osascript)
            try:
                if sys.platform.startswith("win"):
                    t = str(titulo).replace("\r", " ").replace("\n", " ").replace("'", "''")
                    m = str(mensagem).replace("\r", " ").replace("\n", " ").replace("'", "''")
                    # Escapa $ e aspas para o PowerShell não interpretar
                    t = t.replace("$", "`$")
                    m = m.replace("$", "`$")
                    ps = (
                        "Add-Type -AssemblyName System.Windows.Forms; "
                        "Add-Type -AssemblyName System.Drawing; "
                        "$notify = New-Object System.Windows.Forms.NotifyIcon; "
                        "$notify.Icon = [System.Drawing.SystemIcons]::Information; "
                        "$notify.Visible = $true; "
                        f"$notify.ShowBalloonTip(4000, '{t}', '{m}', [System.Windows.Forms.ToolTipIcon]::Info); "
                        "Start-Sleep -Seconds 5; "
                        "$notify.Dispose()"
                    )
                    subprocess.Popen(
                        ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                    return
                elif sys.platform.startswith("linux"):
                    try:
                        subprocess.Popen(
                            ["notify-send", "-a", "Diamante Roxo", str(titulo), str(mensagem)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        )
                        return
                    except Exception:
                        pass
                    try:
                        subprocess.Popen(
                            ["zenity", "--notification", "--text", f"{titulo}\n{mensagem}"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        )
                    except Exception:
                        pass
                    return
                else:
                    # macOS / outros: osascript
                    try:
                        t = str(titulo).replace("\\", "\\\\").replace('"', '\\"')
                        m = str(mensagem).replace("\\", "\\\\").replace('"', '\\"')
                        subprocess.Popen(
                            ["osascript", "-e", f'display notification "{m}" with title "{t}"'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        )
                    except Exception:
                        pass
            except Exception:
                pass
        threading.Thread(target=_enviar, daemon=True).start()
    except Exception:
        pass

log("Inicializando o Diamante Roxo...")

# === Flags de Global ===
encerrar_sistema = False
sistema_em_andamento = False
sistema_autorizado = False
client = None
event_client = None

# === Rotas para os Arquivos de Controle (pasta principal) ===
painel_geral = os.path.join(diretorio_base, "Painel_de_Controle.txt")
caminho_censura = os.path.join(diretorio_base, "controle_censura.txt")

ultima_modificacao = 0
ultimo_polling = 1  # segundos entre cada ciclo do loop principal
intervalo_detecao = 0.5  # segundos entre cada checagem de censura/skip durante filmes

# === VERIFICAÇÃO ESTRITA DA TRAVA DE SEGURANÇA ===
try:
    if os.path.exists(painel_geral):
        with open(painel_geral, "r", encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if linha and "=" in linha and not linha.startswith("#") and not linha.startswith("="):
                    chave, valor = linha.split("=", 1)
                    if chave.strip() == "executar_sistema":
                        comando = valor.strip().lower()
                        # Só libera se for explicitamente um dos três comandos de desbloqueio
                        if comando in ["yes", "sim", "true"]:
                            sistema_autorizado = True
                        # Se for ["no", "não", "false"] ou qualquer erro de digitação, continua False (bloqueado)
                        break

    if not sistema_autorizado:
        print()
        log("[SISTEMA BLOQUEADO] Comando inválido, negado ou incorreto no Painel de Controle.")
        log("O Diamante Roxo só será iniciado se 'executar_sistema' estiver como: yes, sim ou true.")
        print()
        log("Encerrando por medida de segurança...")
        time.sleep(2)
        exit()
except Exception as e:
    print()
    log(f"[ERRO CRÍTICO] Falha ao verificar a trava de segurança: {e}", toast=True)
    log("Encerrando o sistema imediatamente, por precaução.")
    time.sleep(2)
    exit()

# == Variáveis globais (conexão OBS, modo operação) ==
global_obs_host = "127.0.0.1"
global_obs_port = 4455
global_obs_password = ""
global_modo_sistema = "live"
global_plataforma = "twitch"

# === Modos do Sistema ===
global_modo_conteudo = "filmes"
global_modo_destino = "filmes"
global_modo_raid = "final"
global_saida_rerun = "final"
global_duracao_entrada = "00:00:09"
global_duracao_inicio  = "00:07:05"
global_duracao_raid    = "00:11:10"
global_duracao_final   = "00:05:10"
ultima_modificacao_tempos = 0.0
global_oraculo_ativado = False
global_pausa_apos_filmes = 0
global_pausa_retorno = "05:00:00"
global_oraculo_retorno = "05:00:00"
global_encerrar_apos_filmes = 0
global_pausa_modo_atual = None  # None = PAUSE manual; "quantidade"/"oraculo" = pausa interna ativa
TOLERANCIA_RETORNO_SEGUNDOS = 60  # watchdog: forçar retorno X/Y + 60s se não voltar

# === Sistema do Rerun ===
global_rerun_dias = 1
global_rerun_horario_final = "00:00:00"



_stopping_stream = False  # True enquanto stop_stream() é intencional, evita reação do on_output_state_changed
_reconectando_obs = False  # True enquanto está tentando reconectar ao OBS, evita flood de conexão



# 2) Localização Dinâmica dos Softwares.

def localizar_software(nome_exe):
    mapa = {
        "obs64.exe": [
            r"%ProgramFiles%\obs-studio\bin\64bit\obs64.exe",
            r"%LocalAppData%\obs-studio\bin\64bit\obs64.exe",
        ],
        "Streamer.bot.exe": [
            r"%AppData%\Streamer.bot\app\Streamer.bot.exe",
        ],
        "MixItUp.exe": [
            r"%LocalAppData%\MixItUp\MixItUp.exe",
            r"%AppData%\MixItUp\MixItUp.exe",
        ],
        "Chatty.exe": [
            r"%LocalAppData%\Chatty\Chatty.exe",
            r"%AppData%\Chatty\Chatty.exe",
        ],
    }
    caminhos = mapa.get(nome_exe, [])
    for caminho in caminhos:
        caminho_exp = os.path.expandvars(caminho)
        if os.path.exists(caminho_exp):
            return caminho_exp
        # Wildcard em qualquer trecho do path (ex.: pasta com versão no nome).
        # glob resolve também diretórios intermediários, que o os.path.exists não resolve.
        if any(ch in caminho_exp for ch in "*?"):
            encontrados = sorted(glob.glob(caminho_exp), reverse=True)
            if encontrados:
                return encontrados[0]

    locais_rasos = ["C:\\"]
    locais_profundos = [r"%ProgramFiles%", r"%ProgramFiles(x86)%", r"%AppData%", r"%LocalAppData%", r"%UserProfile%\Documents", r"%UserProfile%\Desktop", r"%UserProfile%\Downloads"]

    def _buscar(locais, max_nivel):
        for p in locais:
            p_exp = os.path.expandvars(p)
            if not os.path.isdir(p_exp):
                continue
            try:
                candidato_raiz = os.path.join(p_exp, nome_exe)
                if os.path.exists(candidato_raiz):
                    return candidato_raiz
                for entrada in os.scandir(p_exp):
                    if entrada.is_dir():
                        nivel1 = os.path.join(entrada.path, nome_exe)
                        if os.path.exists(nivel1):
                            return nivel1
                        if max_nivel >= 2:
                            try:
                                for sub in os.scandir(entrada.path):
                                    if sub.is_dir():
                                        nivel2 = os.path.join(sub.path, nome_exe)
                                        if os.path.exists(nivel2):
                                            return nivel2
                                        if max_nivel >= 3:
                                            try:
                                                for sub2 in os.scandir(sub.path):
                                                    if sub2.is_dir():
                                                        nivel3 = os.path.join(sub2.path, nome_exe)
                                                        if os.path.exists(nivel3):
                                                            return nivel3
                                            except Exception:
                                                pass
                            except Exception:
                                pass
            except Exception:
                pass
        return None

    resultado = _buscar(locais_profundos, 3)
    if resultado:
        return resultado
    return _buscar(locais_rasos, 1)

print()
log("Localizando softwares...")
app_obs64studio = localizar_software("obs64.exe")
app_streamerbot = localizar_software("Streamer.bot.exe")
app_mixitup = localizar_software("MixItUp.exe")
app_chatty = localizar_software("Chatty.exe")

for nome, caminho in [("OBS Studio", app_obs64studio), ("Streamer.bot", app_streamerbot), ("Mix It Up", app_mixitup), ("Chatty", app_chatty)]:
    if caminho:
        log(f"{nome} encontrado em: {caminho}.")
    else:
        log(f"[AVISO] {nome} não encontrado. A inicialização dele será ignorada.")

# 3) Inicialização.

def verificar_app_start(nome_processo):
    for proc in psutil.process_iter(['name']):
        try:
            if nome_processo.lower() in proc.info['name'].lower():
                return True
        except Exception:
            pass
    return False

def start_mixitup():
    if verificar_app_start("MixItUp.exe"):
        log("Mix It Up já está em execução. Pulando a inicialização.")
        return
    if app_mixitup:
        pasta_padrao = os.path.dirname(app_mixitup)
        subprocess.Popen(app_mixitup, cwd=pasta_padrao)
        log("Mix It Up iniciado com sucesso.")
    else:
        log("[ERRO] Mix It Up não encontrado.")

def start_streamerbot():
    if verificar_app_start("Streamer.bot.exe"):
        log("Streamer.bot já está em execução. Pulando a inicialização.")
        return
    if app_streamerbot:
        pasta_padrao = os.path.dirname(app_streamerbot)
        subprocess.Popen(app_streamerbot, cwd=pasta_padrao)
        log("Streamer.bot iniciado com sucesso.")
    else:
        log("[ERRO] Streamer.bot não encontrado.")

def start_obs64studio():
    if verificar_app_start("obs64.exe"):
        log("OBS Studio já está em execução. Pulando a inicialização.")
        return
    if app_obs64studio:
        pasta_padrao = os.path.dirname(app_obs64studio)
        subprocess.Popen(app_obs64studio, cwd=pasta_padrao)
        log("OBS Studio iniciado com sucesso.")
    else:
        log("[ERRO] OBS Studio não encontrado.")

def start_chatty():
    if verificar_app_start("Chatty.exe"):
        log("Chatty já está em execução. Pulando a inicialização.")
        return
    if app_chatty:
        pasta_padrao = os.path.dirname(app_chatty)
        subprocess.Popen(app_chatty, cwd=pasta_padrao)
        log("Chatty iniciado com sucesso.")
    else:
        log("[ERRO] Chatty não encontrado.")

def minimizar_janelas():
    print()
    log("Minimizando janelas...")

    # === OBS Studio ===
    try:
        Desktop(backend="uia").window(title_re="^OBS.*", visible_only=True).minimize()
        log("OBS Studio minimizado.")
    except Exception:
        pass

    # === Streamer.bot ===
    try:
        Desktop(backend="uia").window(title_re="^Streamer.bot.*", visible_only=True).minimize()
        log("Streamer.bot minimizado.")
    except Exception:
        pass

    # === Mix It Up ===
    try:
        Desktop(backend="uia").window(title_re="^Mix It Up.*", visible_only=True).minimize()
        log("Mix It Up minimizado.")
    except Exception:
        pass

    # === Chatty ===
    try:
        Desktop(backend="uia").window(title_re=".*Chatty.*", visible_only=True).minimize()
        log("Janela do Chatty minimizada.")
    except Exception:
        pass

# 4) Interno do OBS Studio.

# === FUNÇÃO AUXILIAR DE SEGURANÇA PARA VOLUME ===
def ajustar_volume_seguro(nome_fonte, volume_multiplicador):
    """
    Ajusta o volume de uma fonte de forma segura com validação.
    
    Args:
        nome_fonte (str): Nome da fonte
        volume_multiplicador (float): Valor entre 0.000001 e 1.5957
    
    Returns:
        bool: True se bem-sucedido, False caso contrário
    """
    global client
    
    if not client:
        log("[VOLUME] O cliente do OBS não está conectado.")
        return False

    try:

        volume_seguro = max(0.000001, min(1.5957, volume_multiplicador))

        # Log detalhado se houve ajuste
        if volume_seguro != volume_multiplicador:
            log(f"[VOLUME] Valor {volume_multiplicador} ajustado para o intervalo seguro: {volume_seguro}.")

        client.set_input_volume(nome_fonte, volume_seguro)
        return True

    except Exception as e:
        log(f"[ERRO VOLUME] Falha ao ajustar o volume de '{nome_fonte}': {e}.")
        return False

class GrampeadoOBS(EventClient):
    fontes_alertas = ["MSG_PIX"]

    def __init__(self, host, port, password):
        super().__init__(host=host, port=port, password=password,
                         subs=Subs.LOW_VOLUME | Subs.INPUTVOLUMEMETERS | Subs.INPUTS | Subs.OUTPUTS)
        self.mixer_mutado = False
        
        orig_trigger = self.callback.trigger
        
        def safe_trigger(event, data):
            if event == "InputVolumeMeters":
                from types import SimpleNamespace
                from obsws_python.util import to_snake_case
                
                raw_inputs = data.get("inputs", [])
                processed_inputs = []
                
                for item in raw_inputs:
                    sn_item = SimpleNamespace(**{to_snake_case(k): v for k, v in item.items()})
                    processed_inputs.append(sn_item)
                
                custom_data = SimpleNamespace(inputs=processed_inputs)
                
                for fn in self.callback._callbacks:
                    if fn.__name__ == "on_input_volume_meters":
                        fn(custom_data)
            else:
                orig_trigger(event, data)
        
        self.callback.trigger = safe_trigger
        self.callback.register([self.on_current_program_scene_changed, self.on_input_volume_meters, self.on_input_mute_state_changed, self.on_output_state_changed])
        
        self.cena_atual = "ENTRADA"
        self.volumes_originais = {}
        self._cache_fontes_cena = {}

        # Estado de transição entre cenas durante um alerta
        # Estrutura: {
        # 'id': int, 'origem': str, 'destino': str, 'modo': str,
        # 'fontes_antigas': [str], 'fontes_novas': [str]
        # }
        self.transicao = None
        self._trans_lock = threading.Lock()
        self._trans_seq = 0

        # volumes_originais é lido/escrito pela thread de eventos do OBS e por
        # threads de threading.Timer ao mesmo tempo. self._trans_lock já protegia
        # self.transicao — este lock faz o mesmo pro "cofre" de volumes.
        self._vol_lock = threading.Lock()

        self.fontes_por_cena = {
            "INÍCIO": ["MÚSICAS"],
            "MÍDIAS": ["SPOTIFY"],
            "PAUSA": ["SPOTIFY", "MÚSICAS"]
        }
        
        self.resgate_em_andamento = False
        self.timer_retorno = None
        self._midia_pausada_pelo_alerta = False
        self._resume_timer = None

        print()
        log("Grampeado do OBS inicializado e aguardando eventos...")

    def _obter_fontes_cena(self, nome_cena):
        if nome_cena in self._cache_fontes_cena:
            return self._cache_fontes_cena[nome_cena]
        fontes = self.fontes_por_cena.get(nome_cena, [])
        resultado = [f for f in fontes if f not in self.fontes_alertas]
        self._cache_fontes_cena[nome_cena] = resultado
        return resultado

    def on_current_program_scene_changed(self, data):
        global global_modo_conteudo, client
        nova_cena = data.scene_name
        prev_cena = self.cena_atual

        # Ignora evento duplicado do OBS (mesma cena)
        if prev_cena == nova_cena:
            return

        # Descobre fontes de ambas as cenas (cacheia automaticamente)
        fontes_antigas = self._obter_fontes_cena(prev_cena)
        fontes_novas = self._obter_fontes_cena(nova_cena)

        log(f"Transição de cena detectada: '{prev_cena}' -> '{nova_cena}'", toast=True)
        _pendente = _consumir_cena_pendente(nova_cena)
        if _pendente is not None:
            log(f"Cena trocada para: {_pendente}")

        # Atualiza cena atual apenas após detectar/registrar a transição
        self.cena_atual = nova_cena
        self._cache_fontes_cena.clear()

        # Se existe um alerta em andamento, tratamos a transição por estado
        if self.resgate_em_andamento:
            log("Alerta ativo durante a transição. Iniciando o fluxo de transição controlada...")

            with self._trans_lock:
                # Se já houver uma transição em andamento diferente, cancela-a
                if self.transicao and (self.transicao.get('origem') != prev_cena or self.transicao.get('destino') != nova_cena):
                    log("Nova transição detectada. Cancelando a transição anterior.")
                    self._cancelar_transicao_locked()

                # Cria nova transição (ou reusa se idêntica)
                if not self.transicao:
                    self._iniciar_transicao_locked(prev_cena, nova_cena, fontes_antigas, fontes_novas, global_modo_conteudo)

            for fonte in fontes_antigas:
                if fonte not in fontes_novas:
                    with self._vol_lock:
                        vol_orig = self.volumes_originais.pop(fonte, None)
                    if vol_orig is not None:
                        threading.Thread(target=self.executar_efeito_fade, args=(fonte, 0.0001, vol_orig, 2), daemon=True).start()
                        print()
                        log(f"[TRANSIÇÃO] Fonte '{fonte}' saiu de cena. Restaurando volume...")

            # Aplica as ações imediatas da transição (sem finalizar o alerta aqui)
            try:
                if global_modo_conteudo == 'filmes':
                    self._aplicar_transicao_filmes(prev_cena, nova_cena)
                else:
                    self._aplicar_transicao_rerun(fontes_antigas, fontes_novas)
            except Exception as e:
                log(f"Erro ao aplicar transição imediata: {e}")

    _ultimo_metro_volume = 0

    def on_input_volume_meters(self, data):
        agora = time.monotonic()
        if agora - self._ultimo_metro_volume < 0.1:
            return
        self._ultimo_metro_volume = agora

        if self.mixer_mutado:
            return
        
        if not hasattr(data, "inputs"): 
            return

        global client
        if not client:
            return

        try:
            for input_data in data.inputs:
                if hasattr(input_data, 'input_name') and input_data.input_name in self.fontes_alertas:
                    if hasattr(input_data, "input_levels_mul") and input_data.input_levels_mul:
                        vol_multiplier = max(canal[1] for canal in input_data.input_levels_mul)
                    else:
                        vol_multiplier = 0.0

                    vol_acima_limite = vol_multiplier > 0.00316

                    if vol_acima_limite:
                        if self.timer_retorno:
                            self.timer_retorno.cancel()
                            self.timer_retorno = None

                        if not self.resgate_em_andamento:
                            self.resgate_em_andamento = True
                            self.aplicar_acao_inicial()
                    else:
                        if self.resgate_em_andamento and not self.timer_retorno:
                            self.timer_retorno = threading.Timer(3.0, self.finalizar_resgate_com_seguranca)
                            self.timer_retorno.start()
        except Exception as e:
            log(f"[ERRO] Falha ao processar os medidores de volume (InputVolumeMeters): {e}.")

    def aplicar_acao_inicial(self):
        global client, global_modo_conteudo

        # CENA MÍDIAS + MODO FILME
        if self.cena_atual == "MÍDIAS" and global_modo_conteudo == "filmes":
            try:
                client.trigger_media_input_action("FILMES", "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PAUSE")
                self._midia_pausada_pelo_alerta = True
                print()
                log("Cena MÍDIAS (Filmes): Resgate detectado. Mídia pausada.", toast=True)
            except Exception as e:
                print()
                log(f"Erro ao pausar a mídia no OBS: {e}.")

        # OUTRAS CENAS (redução automática de volume para TODAS as fontes de áudio, exceto as de alerta)
        else:
            fontes_cena = self._obter_fontes_cena(self.cena_atual)
            if not fontes_cena:
                log(f"Cena {self.cena_atual}: nenhuma fonte de áudio encontrada para a redução automática de volume.")

            for nome_fonte in fontes_cena:
                try:
                    status_vol = client.get_input_volume(nome_fonte)

                    with self._vol_lock:
                        if nome_fonte not in self.volumes_originais:
                            if hasattr(status_vol, 'input_volume_db'):
                                db_atual = status_vol.input_volume_db
                                self.volumes_originais[nome_fonte] = 10 ** (db_atual / 20.0)
                            else:
                                self.volumes_originais[nome_fonte] = 1.0
                                log(f"[AVISO] Não foi possível obter o volume em dB da fonte '{nome_fonte}'. Usando o padrão 1.0.")

                    sucesso = ajustar_volume_seguro(nome_fonte, 0.031622)

                    if sucesso:
                        log(f"Cena {self.cena_atual}: Resgate detectado. Volume de '{nome_fonte}' reduzido para -30 dB.")
                    else:
                        log(f"Cena {self.cena_atual}: falha ao reduzir o volume de '{nome_fonte}'.")

                except Exception as e:
                    log(f"Erro ao ajustar o volume da fonte '{nome_fonte}' no OBS: {e}.")

    def finalizar_resgate_com_seguranca(self):
        global client, global_modo_conteudo
        print()
        log("[SISTEMA] Timer de 3 segundos esgotado. Finalizando o resgate com segurança.")

        self.resgate_em_andamento = False
        self.timer_retorno = None

        # 1⃣ COFRE DE VOLUMES (Proteção máxima contra TypeError)
        try:
            # Captura e limpa o cofre como uma operação só, protegido por lock —
            # finalizar_resgate_com_seguranca roda tanto pela thread de eventos do
            # OBS quanto disparada por threading.Timer, então sem lock dava pra
            # perder ou duplicar uma entrada se as duas caíssem ao mesmo tempo.
            with self._vol_lock:
                itens_para_restaurar = list(self.volumes_originais.items())
                self.volumes_originais.clear()

            if itens_para_restaurar:
                for fonte, vol_original in itens_para_restaurar:
                    log(f"Alerta concluído. Iniciando a restauração gradativa de '{fonte}' para o volume original...")
                    threading.Thread(target=self.executar_efeito_fade, args=(fonte, 0.031622, vol_original, 2), daemon=True).start()
            else:
                log("Nenhum volume de áudio pendente para restaurar.")
        except Exception as e:
            log(f"Erro ignorado ao tentar restaurar volumes: {e}.")

        # 2⃣ RETOMADA DE MÍDIAS (Play dinâmico)
        try:
            # Delegar a retomada/limpeza de transição para o helper centralizado
            self._finalizar_transicao()
        except Exception as e:
            log(f"[TRANSIÇÃO] Erro ao finalizar a transição pelo auxiliar: {e}.")

    def executar_efeito_fade(self, nome_fonte, vol_inicial_mul, vol_final_mul, duracao):
        global client
        
        vol_inicial_mul = max(0.000001, min(1.5957, vol_inicial_mul))
        vol_final_mul = max(0.000001, min(1.5957, vol_final_mul))
        
        passos = 8
        intervalo = duracao / passos
        subida_por_passos = (vol_final_mul - vol_inicial_mul) / passos

        volume_atual_mul = vol_inicial_mul
        tentativas_falhadas = 0
        
        for passo in range(passos):
            time.sleep(intervalo)
            volume_atual_mul += subida_por_passos
            
            volume_atual_mul = max(0.000001, min(1.5957, volume_atual_mul))
            
            # Usar função segura
            if not ajustar_volume_seguro(nome_fonte, volume_atual_mul):
                tentativas_falhadas += 1
                if tentativas_falhadas >= 3:
                    log("[DESVANECIMENTO] Abortado após 3 falhas consecutivas.")
                    break

        # Último ajuste para garantir o volume exato ao final do desvanecimento
        vol_final_mul = max(0.000001, min(1.5957, vol_final_mul))
        if ajustar_volume_seguro(nome_fonte, vol_final_mul):
            print()
            log(f"Desvanecimento concluído. Volume da fonte '{nome_fonte}' restaurado com sucesso.")
        else:
            print()
            log(f"Erro ao finalizar o desvanecimento na fonte '{nome_fonte}'.")

    # ----------------- Helpers de Transição -----------------
    def _iniciar_transicao_locked(self, origem, destino, fontes_antigas, fontes_novas, modo):
        """Cria e registra uma nova transição. Deve ser chamado com o lock adquirido."""
        self._trans_seq += 1
        self.transicao = {
            'id': self._trans_seq,
            'origem': origem,
            'destino': destino,
            'modo': modo,
            'fontes_antigas': fontes_antigas,
            'fontes_novas': fontes_novas,
        }
        log(f"[TRANSIÇÃO] Iniciada transição #{self.transicao['id']}: {origem} -> {destino} (modo={modo})")

    def _cancelar_transicao_locked(self):
        """Marca transição como cancelada. Deve ser chamado com o lock adquirido."""
        if self.transicao:
            log(f"[TRANSIÇÃO] Transição #{self.transicao.get('id')} cancelada.")
            self.transicao = None

    def _aplicar_transicao_filmes(self, origem, destino):
        """Ações imediatas ao transitarmos enquanto há alerta no modo FILMES."""
        global client, global_modo_conteudo
        if destino != "MÍDIAS":
            return
        try:
            client.trigger_media_input_action("FILMES", "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PAUSE")
            self._midia_pausada_pelo_alerta = True
            log(f"[TRANSIÇÃO] Modo FILMES: mídia 'FILMES' pausada durante a transição {origem} -> {destino}.")
        except Exception as e:
            log(f"[TRANSIÇÃO] Falha ao pausar a mídia na transição: {e}.")

    def _aplicar_transicao_rerun(self, fontes_antigas, fontes_novas):
        """Ações imediatas ao transitarmos enquanto há alerta no modo RERUN."""
        # Em RERUN não pausamos mídia (não há vídeo reproduzindo). Apenas fazemos o desvanecimento de saída
        # das fontes de áudio que acabaram de entrar na cena, para evitar pico de volume.
        # Faz o desvanecimento de saída de TODA fonte que entrou na nova cena (não estava na anterior)
        fontes_entraram = [f for f in fontes_novas if f not in fontes_antigas]
        for fonte in fontes_entraram:
            try:
                with self._vol_lock:
                    if fonte not in self.volumes_originais:
                        try:
                            vol = client.get_input_volume(fonte).input_volume_mul
                            self.volumes_originais[fonte] = vol
                        except Exception:
                            self.volumes_originais[fonte] = 1.0
                    vol_partida = self.volumes_originais.get(fonte, 1.0)
                threading.Thread(target=self.executar_efeito_fade, args=(fonte, vol_partida, 0.0001, 2), daemon=True).start()
                log(f"[TRANSIÇÃO] Modo RERUN: iniciado o desvanecimento de saída de '{fonte}' (nova na cena).")
            except Exception as e:
                log(f"[TRANSIÇÃO] Falha ao aplicar o desvanecimento de saída em '{fonte}': {e}")

    def _finalizar_transicao(self):
        """Finaliza e limpa o estado de transição — deve ser chamado quando o alerta terminar."""
        global client, global_modo_conteudo
        with self._trans_lock:
            if self.transicao:
                trans = self.transicao
                self.transicao = None
            else:
                trans = None

        if trans:
            log(f"[TRANSIÇÃO] Finalizando a transição #{trans.get('id')}: {trans.get('origem')} -> {trans.get('destino')}.")

        try:
            # Retomar FILMES se foi pausado pelo alerta e estamos na cena MÍDIAS
            if self._midia_pausada_pelo_alerta:
                if global_modo_conteudo == 'filmes' and self.cena_atual == 'MÍDIAS':
                    try:
                        client.trigger_media_input_action('FILMES', 'OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PLAY')
                        log("[TRANSIÇÃO] Mídia 'FILMES' retomada após o fim do alerta.")
                    except Exception as e:
                        log(f"[TRANSIÇÃO] Erro ao retomar a mídia 'FILMES': {e}.")
                self._midia_pausada_pelo_alerta = False

        except Exception as e:
            log(f"[TRANSIÇÃO] Erro ao finalizar a transição: {e}.")

    def on_input_mute_state_changed(self, data):
        try:
            if data.input_name in self.fontes_alertas:
                if data.input_muted:
                    print()
                    log(f"[GRAMPEADOR] '{data.input_name}' silenciado (Barra Cinza). Interrompendo os ciclos.")
                    self.mixer_mutado = True

                    if self.resgate_em_andamento:
                        if self.timer_retorno:
                            self.timer_retorno.cancel()
                            self.timer_retorno = None

                        self.finalizar_resgate_com_seguranca()
                        self.resgate_em_andamento = False
                else:
                    print()
                    log(f"[GRAMPEADOR] '{data.input_name}' ativado (Barra Verde). Sensores reativados.")
                    self.mixer_mutado = False
                    self.resgate_em_andamento = False
        except AttributeError:
            pass

    def on_output_state_changed(self, data):
        global _stopping_stream
        try:
            output_name = data.output_name
            output_state = data.output_state
        except AttributeError:
            return

        if 'stream' not in output_name.lower():
            return

        if 'STOPPED' in output_state and not _stopping_stream:
            if self._resume_timer:
                self._resume_timer.cancel()
                self._resume_timer = None
            if sistema_em_andamento:
                print()
                log("[OBS] A transmissão caiu. Pausando o filme...")
                pausar_filme_se_rodando()
        elif 'STARTED' in output_state:
            if self._resume_timer:
                self._resume_timer.cancel()
            self._resume_timer = threading.Timer(3.0, self._retomar_filme_seguro)
            self._resume_timer.daemon = True
            self._resume_timer.start()

    def _retomar_filme_seguro(self):
        self._resume_timer = None
        if sistema_em_andamento:
            print()
            log("[OBS] Transmissão estável há 3 s. Retomando o filme...")
            retomar_filme_se_pausado()

# === Conecta ao OBS via WebSocket ===

def conectar_obs():
    global client, event_client, global_obs_host, global_obs_port, global_obs_password

    if client is not None:
        print()
        log("Conexão com o OBS já estabelecida. Mantendo a conexão atual para evitar duplicidade.")
        return True

    try:
        client = ReqClient(host= global_obs_host,
                           port=global_obs_port,
                           password=global_obs_password)
        print()
        log(f"Conectado ao OBS com sucesso em {global_obs_host}:{global_obs_port}.")

        event_client = GrampeadoOBS(host=global_obs_host,
                                    port=global_obs_port,
                                    password=global_obs_password)

        return True

    except Exception as e:
        print()
        log(f"Falha ao conectar no OBS ({global_obs_host}): {e}.")
        client = None
        event_client = None
        return False

def pausar_filme_se_rodando():
    if global_modo_conteudo == "filmes" and sistema_em_andamento:
        try:
            cena = client.get_current_program_scene().current_program_scene_name
            if cena == "MÍDIAS":
                client.trigger_media_input_action("FILMES", "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PAUSE")
                log("[GRAMPEADO] Filme pausado.")
        except Exception:
            pass


def retomar_filme_se_pausado():
    if global_modo_conteudo == "filmes" and sistema_em_andamento:
        try:
            cena = client.get_current_program_scene().current_program_scene_name
            if cena == "MÍDIAS":
                client.trigger_media_input_action("FILMES", "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PLAY")
                log("[GRAMPEADO] Filme retomado.")
        except Exception:
            pass


# === Inicialização de Transmissão/Gravação ===

def esperar(tempo_str, cena_esperada, nome_fonte="FILMES", is_midia=False, duracao_proximo_seg=0, lista_saltos=None, lista_censuras=None, indice_filme=0):
    total_segundos = converter_hhmmss(tempo_str)
    if total_segundos is None:
        print()
        log(f"[ERRO] Tempo inválido no tempo_duracao.txt: {tempo_str!r}. Esperado HH:MM:SS ou HH:MM:SS:MS. Pulando este filme.", toast=True)
        return None
    # Conta o tempo desde a troca de cena (o cronômetro já correu durante a transição),
    # dando tempo para a thread do OBS registrar "Transição de cena" antes do "Aguardando".
    _inicio_contagem = time.time()
    time.sleep(0.5)
    _pendente = _consumir_cena_pendente()
    if _pendente is not None:
        log(f"Cena trocada para: {_pendente}")
    print()
    log(f"Aguardando {tempo_str}...")
    return esperar_com_deteccao(total_segundos, cena_esperada, nome_fonte, is_midia, duracao_proximo_seg, lista_saltos, lista_censuras, indice_filme, _inicio_contagem)

def start_sistema():
    global client, sistema_em_andamento, global_modo_sistema, global_modo_conteudo

    if sistema_em_andamento:
        print()
        log("Sistema já está em andamento. Pulando o início.")
        return

    if client is None:
        if not conectar_obs():
            print()
            log("[ERRO] Não foi possível conectar ao OBS no horário definido.")
            return

    # Inicia transmissão/gravação no OBS
    if global_modo_sistema in ["gravar", "gravação", "gravacao", "record", "teste"]:
        try:
            client.start_record()
        except Exception as e:
            if "500" in str(e) or "already" in str(e).lower():
                log("O OBS já está gravando. Seguindo sem erro.")
            else:
                raise
        print()
        log("Gravação sendo iniciada.", toast=True)
    elif global_modo_sistema == "live":
        try:
            client.start_stream()
        except Exception as e:
            if "500" in str(e) or "already" in str(e).lower():
                log("O OBS já está transmitindo. Seguindo sem erro.")
            else:
                raise
        print()
        log("Transmissão sendo iniciada.", toast=True)
    else:
        print()
        log(f"[ERRO] Modo de sistema inválido: {global_modo_sistema!r}. "
            "Use 'live' ou 'gravar'. Nada foi iniciado.")
        return

    # Inicia o fluxo: thread de cenas, e começa pela ENTRADA (9s)
    iniciar_fluxo()

def iniciar_fluxo():
    global sistema_em_andamento, global_modo_conteudo

    sistema_em_andamento = True
    threading.Thread(target=aba_geral, daemon=True).start()

def resetar_fluxo():
    print()
    log("Resetando o fluxo para o início.")
    iniciar_fluxo()

# === Controle de Cenas/Fontes ===

def trocar_cena(nome):
    global _cena_pendente_log
    client.set_current_program_scene(nome)
    # Loga "Cena trocada" só depois da "Transição" (handler do OBS), com fallback
    with _cena_lock:
        _cena_pendente_log = nome
    def _flush_cena():
        valor = _consumir_cena_pendente(nome)
        if valor is not None:
            log(f"Cena trocada para: {valor}")
    threading.Timer(1.5, _flush_cena).start()

def cena_ativa_obs():
    return client.get_current_program_scene().current_program_scene_name

# == Estado global de reprodução de mídia (índice, tempo decorrido, detecção de skip) ==
midia_idx_global = 0
midia_decorrido_global = 0.0
timeline_vlc_global = -1

# === SISTEMA DE CENSURA DINÂMICA ===
def converter_hhmmss_tupla(texto):
    """Valida 'HH:MM:SS' ou 'HH:MM:SS:MS' e devolve (h, m, s, ms), ou None se for inválido.

    MS é opcional: se não houver, devolve 0. Usado para durações de filme,
    censura e tempos de cena, onde a precisão de milissegundos importa.
    """
    partes = texto.strip().split(":")
    if len(partes) not in (3, 4):
        return None
    try:
        h, m, s = (int(p) for p in partes[:3])
        ms = int(partes[3]) if len(partes) == 4 else 0
    except ValueError:
        return None
    if not (0 <= h < 24 and 0 <= m < 60 and 0 <= s < 60 and 0 <= ms < 1000):
        return None
    return h, m, s, ms


def converter_hhmmss(texto):
    """Converte 'HH:MM:SS' ou 'HH:MM:SS:MS' em segundos (float se houver MS).

    Devolve None quando o formato não é válido, em vez de estourar erro.
    Usado para validar o tempo_duracao.txt e o controle_censura.txt antes
    de qualquer conta, para que um .txt mal digitado não derruba a sessão.
    """
    horario = converter_hhmmss_tupla(texto)
    if horario is None:
        return None
    h, m, s, ms = horario
    return h * 3600 + m * 60 + s + (ms / 1000.0)


def carregar_censuras_do_filme(indice_filme):
    lista_censuras = []
    if not os.path.exists(caminho_censura):
        return lista_censuras
        
    try:
        linhas_validas = []
        with open(caminho_censura, "r", encoding="utf-8") as f:
            for linha in f:
                linha_limpa = linha.strip()
                if linha_limpa and not linha_limpa.startswith("#") and not linha_limpa.startswith("="):
                    linhas_validas.append(linha_limpa)
            
        if indice_filme < len(linhas_validas):
            linha_comando = linhas_validas[indice_filme]
            
            if "|" in linha_comando:
                partes_principais = linha_comando.split("|")
                status_linha = partes_principais[0].strip().lower() == "true"
                
                if not status_linha:
                    return lista_censuras
                
                conteudo_censuras = partes_principais[1].strip()
                blocos = conteudo_censuras.split(";")
                
                for bloco in blocos:
                    if ">" not in bloco:
                        continue
                    definicoes = bloco.split(">")
                    if len(definicoes) != 3:
                        print()
                        log(f"[AVISO] Filme {indice_filme + 1}: trecho de censura descartado. "
                            f"Esperado INÍCIO > FIM > FONTE -> {bloco.strip()!r}")
                        continue
                    try:
                        inicio = converter_hhmmss(definicoes[0])
                        fim = converter_hhmmss(definicoes[1])
                        if inicio is None or fim is None:
                            raise ValueError("tempo fora do formato HH:MM:SS ou HH:MM:SS:MS")
                        if fim <= inicio:
                            raise ValueError(f"FIM ({fim} s) precisa ser maior que INÍCIO ({inicio} s)")
                        # Suporta múltiplas fontes separadas por vírgula
                        # Divide pelas vírgulas se houver; senão pega apenas o nome único
                        lista_fontes = [f.strip() for f in definicoes[2].strip().split(",") if f.strip()]
                        if not lista_fontes:
                            raise ValueError("nenhuma fonte informada")
                    except Exception as erro:
                        # Um trecho ruim não descarta os outros do mesmo filme
                        print()
                        log(f"[AVISO] Filme {indice_filme + 1}: trecho de censura descartado "
                            f"({erro}) -> {bloco.strip()!r}")
                        continue

                    for fonte in lista_fontes:
                        lista_censuras.append({
                            "inicio": inicio,
                            "fim": fim,
                            "fonte": fonte,
                            "ativo_agora": False
                        })
    except Exception as e:
        print()
        log(f"Erro ao processar a censura no Filme {indice_filme + 1}: {e}.")

    return lista_censuras

def esperar_com_deteccao(segundos, cena_esperada, nome_fonte=None, is_midia=False, duracao_proximo_seg=0, lista_saltos=None, lista_censuras=None, indice_filme=0, inicio_externo=None):
    global _reconectando_obs, _contagem_ativa
    global midia_idx_global, midia_decorrido_global, timeline_vlc_global, global_oraculo_ativado, global_pausa_apos_filmes
    global global_duracao_entrada, global_duracao_inicio, global_duracao_raid, global_duracao_final, ultima_modificacao_tempos
    decorrido_total = midia_decorrido_global if is_midia else 0.0
    inicio = inicio_externo if inicio_externo is not None else time.time()
    inicio_linha = time.strftime("%H:%M")  # Fixo: horário em que esta seção começou
    
    if is_midia:
        timeline_vlc_global = -1
    
    proximo_recusado = False
    playback_state_atual = None
    ultimo_cursor = None
    contagem_parado = 0
    parado_recente = False
    ultimo_parado_ts = 0.0
    resultado_final = "normal"

    while True:
        agora = time.time()

        if is_midia and nome_fonte:
            try:
                status_obs = client.get_media_input_status(nome_fonte)
                cursor_atual = status_obs.media_cursor if hasattr(status_obs, 'media_cursor') else None
                if hasattr(status_obs, 'playback_state'):
                    playback_state_atual = status_obs.playback_state
                elif hasattr(status_obs, 'playbackState'):
                    playback_state_atual = status_obs.playbackState
                _estado_up = str(playback_state_atual or "").upper()
                if "STOPPED" in _estado_up or "ENDED" in _estado_up or "ERROR" in _estado_up or "NONE" in _estado_up:
                    parado_recente = True
                    ultimo_parado_ts = time.time()
                if cursor_atual is not None:
                    decorrido = cursor_atual / 1000.0
                    if ultimo_cursor is not None and cursor_atual == ultimo_cursor:
                        contagem_parado += 1
                    else:
                        contagem_parado = 0
                    ultimo_cursor = cursor_atual

                    if decorrido_total > 0 and decorrido < decorrido_total - 5:
                        try:
                            client.set_media_input_cursor(nome_fonte, int(decorrido_total * 1000))
                        except Exception:
                            pass
                        decorrido = decorrido_total

                    if timeline_vlc_global >= 0:
                        salto_para_tras = timeline_vlc_global - cursor_atual
                        # Filtro: reinício da fonte (estava parado) = re-sincroniza sem avançar.
                        # Next no VLC (tocando, sem parado) = avança a SESSÃO. Rewind = re-sincroniza.
                        reset_inicio = cursor_atual <= 2000 and salto_para_tras > 300
                        salto_grande = salto_para_tras > 15000 and timeline_vlc_global > 5000
                        if reset_inicio or salto_grande:
                            prev_ms = timeline_vlc_global
                            timeline_vlc_global = cursor_atual
                            _veio_de_parado = parado_recente and (time.time() - ultimo_parado_ts < 3.0)
                            if _veio_de_parado:
                                # OBS voltou pro primeiro vídeo (fonte mexida): como se tivesse começado do zero
                                if is_midia:
                                    midia_idx_global = 0
                                    midia_decorrido_global = 0.0
                                resultado_final = "reset_primeiro"
                                log("[AVISO] VLC voltou para o primeiro vídeo. Reiniciando da SESSÃO 01 como se tivesse começado.", toast=True)
                                parado_recente = False
                                break
                            if salto_grande and not reset_inicio:
                                # Rewind dentro do mesmo filme: re-sincroniza, nao avanca
                                if is_midia:
                                    midia_decorrido_global = 0.0
                                    decorrido_total = 0.0
                                    inicio = time.time()
                                log(f"[AVISO] VLC deu um salto para trás. Re-sincronizando a SESSÃO {indice_filme + 1:02d} sem avançar.", toast=True)
                                parado_recente = False
                                continue
                            # Tocando + voltou pro 0 = skip manual real -> avanca
                            if is_midia: midia_decorrido_global = 0.0
                            resultado_final = "skip_detectado"
                            log(f"Skip manual - SESSAO {indice_filme + 1:02d} | {_fmt_hms(prev_ms / 1000)} -> {_fmt_hms(cursor_atual / 1000)}", toast=True)
                            parado_recente = False
                            break

                    timeline_vlc_global = cursor_atual
                else:
                    parado_recente = True
                    ultimo_parado_ts = time.time()
                    decorrido = decorrido_total + (agora - inicio)
            except Exception:
                # Conexão com o OBS caiu durante o filme: pausar, salvar posição e tentar reconectar
                print()
                log("[ERRO] Conexão com o OBS perdida durante a reprodução. Pausando o filme e tentando reconectar...", toast=True)
                try:
                    client.trigger_media_input_action("FILMES", "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PAUSE")
                    log("[RECONEXÃO] Filme pausado devido à perda de conexão com o OBS.")
                except Exception:
                    pass  # Se não conseguiu pausar, segue tentando reconectar

                # Loop de reconexão com o OBS
                while not encerrar_sistema and not _reconectando_obs:
                    _reconectando_obs = True
                    try:
                        if conectar_obs():
                            log("[RECONEXÃO] Reconectado ao OBS com sucesso.", toast=True)
                            # Restaurar a posição do filme e dar play
                            try:
                                if midia_decorrido_global > 0:
                                    client.set_media_input_cursor("FILMES", int(midia_decorrido_global * 1000))
                                    time.sleep(0.3)
                                    client.trigger_media_input_action("FILMES", "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PLAY")
                                    log(f"[RECONEXÃO] Filme retomado do segundo {int(midia_decorrido_global)}.")
                                else:
                                    # Não tinha tempo decorrido salvo, apenas tenta retomar do início
                                    client.trigger_media_input_action("FILMES", "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PLAY")
                                    log("[RECONEXÃO] Filme retomado do início.")
                            except Exception as e:
                                log(f"[ERRO] Falha ao retomar o filme após a reconexão: {e}.")
                            break  # Sai do loop de reconexão
                        else:
                            log("[RECONEXÃO] Tentativa de reconexão falhou. Tentando novamente em 5 segundos...")
                    except Exception as e:
                        log(f"[ERRO] Erro durante a tentativa de reconexão: {e}.")
                    finally:
                        _reconectando_obs = False

                    if not encerrar_sistema:
                        time.sleep(5)  # Espera 5 s antes de tentar novamente
                decorrido = decorrido_total + (agora - inicio)
        else:
            decorrido = decorrido_total + (agora - inicio)

        # === ATIVAÇÃO DE CENSURA/TARJA ===
        if is_midia and lista_censuras:
            for censura in lista_censuras:
                deve_ativar = censura["inicio"] <= decorrido <= censura["fim"]
                if deve_ativar != censura["ativo_agora"]:
                    visibilidade_fonte(cena_esperada, censura["fonte"], deve_ativar)
                    censura["ativo_agora"] = deve_ativar
                    if deve_ativar:
                        log(f"Censura ativada - SESSÃO {indice_filme + 1:02d} | {censura['fonte']} | {_fmt_hms(decorrido)}", toast=True)

        if is_midia and lista_saltos:
            for salto in lista_saltos:
                if not salto["feito"] and decorrido >= salto["gatilho"]:
                    try:
                        ms_destino = int(salto["destino"] * 1000)
                        client.set_media_input_cursor(nome_fonte, ms_destino)
                        print()
                        log(f"Pós-crédito detectado! SESSÃO {indice_filme + 1:02d} | Saltando para: {_fmt_hms(salto['destino'])}", toast=True)
                        
                        diferenca_salto = salto["destino"] - salto["gatilho"]
                        inicio -= diferenca_salto 
                        decorrido += diferenca_salto
                        salto["feito"] = True 
                    except Exception as e:
                        print()
                        log(f"Erro ao saltar mídia no OBS: {e}")

        if decorrido >= segundos:
            print(f"\n[OK] Tempo concluído: {cena_esperada} finalizada.")
            if is_midia: midia_decorrido_global = 0.0
            resultado_final = "normal"
            break
        
        restante = int(segundos - decorrido)

        if is_midia and global_oraculo_ativado:
            time_atual = time.localtime()
            hora_int = time_atual.tm_hour

            if 30 < restante <= 60:
                segundos_atuais = hora_int * 3600 + time_atual.tm_min * 60 + time_atual.tm_sec
                limite_23h = 23 * 3600
                if (6 <= hora_int < 23) and duracao_proximo_seg > 0:
                    if (segundos_atuais + restante + duracao_proximo_seg) >= limite_23h:
                        proximo_recusado = True

            elif restante <= 30:
                ja_passou_das_23h = (hora_int >= 23 or hora_int <= 6)
                ultimo_filme = (duracao_proximo_seg == 0)
                if proximo_recusado or (ja_passou_das_23h and not ultimo_filme):
                    midia_decorrido_global = decorrido
                    if ja_passou_das_23h:
                        resultado_final = "pausa_horario"
                    else:
                        resultado_final = "pausa_oraculo"
                    break

        # == Pausa por Quantidade de Filmes (detecta 30s antes do fim, igual oráculo) ==
        if is_midia and global_pausa_apos_filmes > 0 and restante <= 30 and decorrido_total == 0:
            if indice_filme + 1 == global_pausa_apos_filmes:
                midia_decorrido_global = decorrido
                resultado_final = "pausa_quantidade"
                break

        # ENTRADA também mostra contagem regressiva
        if True:
            # Exibição arredonda ao segundo mais próximo: começa mostrando o total
            # e chega a 00:00:00 no fim. O 'restante' lógico acima continua no piso,
            # para não mexer nos cortes do Oráculo/pausa; o fim real segue sendo decorrido >= segundos.
            restante_exib = max(0, int(round(segundos - decorrido)))
            mins, secs = divmod(restante_exib, 60)
            horas, mins = divmod(mins, 60)
            agora_dt = datetime.now()
            fim_dt = agora_dt + timedelta(seconds=restante_exib)
            fim_str = fim_dt.strftime("%H:%M")
            em_resgate = event_client and event_client.resgate_em_andamento
            pausado_media = playback_state_atual is not None and "pause" in str(playback_state_atual).lower()
            if is_midia and contagem_parado >= 2:
                pausado_media = True
            estado = "Pausado" if (em_resgate or pausado_media) else "Rodando"
            corte = "Sim" if proximo_recusado else "Não"
            saltos_total = len(lista_saltos) if (is_midia and lista_saltos) else 0
            saltos_feitos = sum(1 for s in lista_saltos if s.get("feito")) if saltos_total else 0
            saltos_str = f"{saltos_feitos}/{saltos_total}" if saltos_total else "0/0"
            # \r no início garante posicionamento correto mesmo após outros logs
            if is_midia:
                print(f"\r{inicio_linha} | Restante: {horas:02d}:{mins:02d}:{secs:02d} | Pós-créditos: {saltos_str} | Corte: {corte} | {estado} | Fim: {fim_str}   ", end="", flush=True)
            else:
                print(f"\r{inicio_linha} | Restante: {horas:02d}:{mins:02d}:{secs:02d} | Fim: {fim_str}   ", end="", flush=True)
            _contagem_ativa = True
        
        try:
            if cena_ativa_obs() != cena_esperada:
                if is_midia:
                    midia_decorrido_global = decorrido
                resultado_final = "pular"
                break
        except Exception:
            pass
        
        # 0.5s entre deteccoes (intervalo_detecao): chamadas ao OBS moderadas por hora de filme,
        # sem atrasar deteccao de skip/censura (o trigger e abrupto, pega na proxima)
        time.sleep(intervalo_detecao)
        
        # --- Reload dos tempos de cena a cada ciclo (fora de MÍDIAS) ---
        # Isso NÃO interfere no loop de censura/skip, apenas atualiza as variáveis
        # se o painel foi alterado recentemente.
        if not is_midia:
            try:
                mtempo = os.path.getmtime(painel_geral)
                if mtempo != ultima_modificacao_tempos:
                    config = {}
                    with open(painel_geral, "r", encoding="utf-8") as f:
                        for linha in f:
                            linha = linha.strip()
                            if linha and "=" in linha and not linha.startswith("#") and not linha.startswith("="):
                                chave, valor = linha.split("=", 1)
                                config[chave.strip()] = valor.strip()
                    global_duracao_entrada = config.get("duracao_entrada", global_duracao_entrada).strip()
                    global_duracao_inicio  = config.get("duracao_inicio",  global_duracao_inicio).strip()
                    global_duracao_raid    = config.get("duracao_raid",    global_duracao_raid).strip()
                    global_duracao_final   = config.get("duracao_final",   global_duracao_final).strip()

                    # Aplica na hora na cena EM EXECUÇÃO (INÍCIO / RAID / FINAL).
                    # ENTRADA e MÍDIAS ficam fora de propósito.
                    chave_tempo = {"INÍCIO": "duracao_inicio",
                                   "RAID": "duracao_raid",
                                   "FINAL": "duracao_final"}.get(cena_esperada)
                    if chave_tempo:
                        valor_tempo = config.get(chave_tempo, "").strip()
                        novo_segundos = converter_hhmmss(valor_tempo)
                        if novo_segundos is not None and novo_segundos > 0 and novo_segundos != segundos:
                            log(f"Tempo {cena_esperada} alterado durante a cena: {segundos} s -> {valor_tempo} "
                                "(contagem reiniciada).")
                            segundos = novo_segundos
                            # Zera o que já correu: o cronômetro volta para o valor
                            # digitado (decorrido = decorrido_total + agora - início;
                            # com decorrido_total = 0 em cena não-MÍDIAS, recalcular
                            # a partir de 'início = agora' zera o decorrido).
                            inicio = time.time()

                    ultima_modificacao_tempos = mtempo
            except Exception:
                pass

    # === LIMPEZA DE SEGURANÇA (CENSURA) ===
    if is_midia and lista_censuras:
        fontes_proximas = set()
        if resultado_final == "normal":
            proximas_censuras = carregar_censuras_do_filme(indice_filme + 1)
            fontes_proximas = {c["fonte"] for c in proximas_censuras}

        for censura in lista_censuras:
            if censura["ativo_agora"] and censura["fonte"] not in fontes_proximas:
                try:
                    visibilidade_fonte(cena_esperada, censura["fonte"], False)
                except Exception:
                    pass
                    
    if _contagem_ativa:
        print()
        _contagem_ativa = False
    return resultado_final

def rotear_pulo():
    global event_client
    nova_cena = cena_ativa_obs()
    print()
    log(f"Roteamento: iniciando o cronômetro da cena '{nova_cena}'.")

    # Segurança: se a cena de destino é RAID ou FINAL, aguarda os alertas terminarem
    # para não interromper o resgate com uma troca de cena brusca.
    if nova_cena in ("RAID", "FINAL"):
        if event_client and event_client.resgate_em_andamento:
            log(f"[SEGURANÇA] Alerta ativo durante o roteamento para '{nova_cena}'. Aguardando...")
            while event_client.resgate_em_andamento:
                time.sleep(0.5)
            log(f"[SEGURANÇA] Alertas concluídos. Prosseguindo para '{nova_cena}'.")

    if nova_cena == "ENTRADA": aba_entrada()
    elif nova_cena == "INÍCIO": aba_inicio()
    elif nova_cena == "MÍDIAS":
        if global_modo_conteudo == "rerun":
            aba_rerun()
        else:
            aba_midias()
    elif nova_cena == "PAUSA": aba_pausa()
    elif nova_cena == "RAID": aba_raid()
    elif nova_cena == "FINAL": aba_final()

def aba_entrada():
    global global_modo_conteudo
    cena = "ENTRADA"

    trocar_cena(cena)
    if esperar(global_duracao_entrada, cena) == "pular":
        print()
        log("Cena ENTRADA mudada manualmente.")
        rotear_pulo()
        return
    aba_inicio()

def aba_inicio():
    cena = "INÍCIO"
    trocar_cena(cena)
    if esperar(global_duracao_inicio, cena) == "pular":
        print()
        log("Cena INÍCIO mudada manualmente.")
        rotear_pulo()
        return
    if global_modo_conteudo == "rerun":
        aba_rerun()
    else:
        aba_midias()

_vis_cache = {}
_vis_estado = {}

def limpar_cache_vis():
    _vis_cache.clear()
    _vis_estado.clear()

def visibilidade_fonte(cena, nome_fonte, visivel):
    try:
        # Só altera e loga se realmente mudou de estado
        estado_atual = _vis_estado.get(cena, {}).get(nome_fonte)
        if estado_atual is not None and estado_atual == visivel:
            return

        if cena not in _vis_cache:
            itens = client.get_scene_item_list(cena).scene_items
            _vis_cache[cena] = itens
        else:
            itens = _vis_cache[cena]
        for item in itens:
            if item['sourceName'] == nome_fonte:
                client.set_scene_item_enabled(cena, item['sceneItemId'], visivel)
                _vis_estado.setdefault(cena, {})[nome_fonte] = visivel
                print()
                _so_tarja_cens = ("TARJA" in nome_fonte.upper() or "CENSURA" in nome_fonte.upper())
                log(f"Fonte '{nome_fonte}' -> {'LIGADA' if visivel else 'DESLIGADA'}", toast=_so_tarja_cens)
                return
            if item.get('isGroup', False) or item.get('is_group', False):
                g_nome = item['sourceName']
                res_g = client.get_group_scene_item_list(g_nome).scene_items
                for sub in res_g:
                    if sub['sourceName'] == nome_fonte:
                        client.set_scene_item_enabled(g_nome, sub['sceneItemId'], visivel)
                        _vis_estado.setdefault(cena, {})[nome_fonte] = visivel
                        print()
                        _so_tarja_cens = ("TARJA" in nome_fonte.upper() or "CENSURA" in nome_fonte.upper())
                        log(f"Fonte '{nome_fonte}' (dentro de '{g_nome}') -> {'LIGADA' if visivel else 'DESLIGADA'}", toast=_so_tarja_cens)
                        return
    except Exception as e:
        print()
        log(f"Erro ao alterar a visibilidade de '{nome_fonte}': {e}.")

def id_sessao(novo_texto):
    try:
        nome_fonte = "SESSÃO ID"

        client.set_input_settings(nome_fonte, {'text': novo_texto}, True)
        print()
        log(f"Sucesso: {nome_fonte} atualizada para {novo_texto}.")

    except Exception as e:
        print()
        log(f"Erro ao atualizar {nome_fonte}: {e}.")

def aba_midias():
    global midia_idx_global, midia_decorrido_global, timeline_vlc_global, event_client, global_encerrar_apos_filmes
    cena = "MÍDIAS"
    fonte_vlc = "FILMES"

    limpar_cache_vis()

    # == Ligando Fontes ==
    visibilidade_fonte(cena, "GIF", True)
    visibilidade_fonte(cena, "STREAMER OFF", True)
    visibilidade_fonte(cena, "FILMES", True)
    visibilidade_fonte(cena, "SESSÃO ID", True)

    # == Desligando Fontes ==
    visibilidade_fonte(cena, "WEBCAM", False)
    visibilidade_fonte(cena, "STREAMER ON", False)
    visibilidade_fonte(cena, "RERUN", False)
    visibilidade_fonte(cena, "SPOTIFY", False)
    visibilidade_fonte(cena, "MÚSICAS", False)
    visibilidade_fonte(cena, "CENSURA", False)
    visibilidade_fonte(cena, "TARJA", False)
    visibilidade_fonte(cena, "EV BRADESCO", False)
    visibilidade_fonte(cena, "WORD_VS", False)
    trocar_cena(cena)

    tempos = arquivo_tempo()
    total = len(tempos)

    # Usa while (e não for) para preservar midia_idx_global entre retomadas e skips
    while midia_idx_global < total:
        i = midia_idx_global
        linha_tempo = tempos[i]

        # === LEITURA DE DURAÇÃO E SALTOS PÓS-CRÉDITOS ===
        tempo_total = linha_tempo.split("|")[0].strip()
        lista_saltos = []  # Reinicia a lista de saltos (pós-crédito) para cada filme

        # Se houver a barra "|", significa que tem pulos cadastrados para esse filme!
        if "|" in linha_tempo:
            partes = linha_tempo.split("|")
            definicoes = partes[1].split(";")
            
            for def_salto in definicoes:
                if ">" in def_salto:
                    s = def_salto.split(">")
                    try:
                        # Extrai gatilho e destino aceitando HH:MM:SS e HH:MM:SS:MS (3 ou 4 partes)
                        gatilho = converter_hhmmss(s[0])
                        destino = converter_hhmmss(s[1])
                        if gatilho is None or destino is None:
                            raise ValueError("tempo fora do formato HH:MM:SS ou HH:MM:SS:MS")

                        # Alimenta a lista de saltos do pacote novo
                        lista_saltos.append({
                            "gatilho": gatilho,
                            "destino": destino,
                            "feito": False
                        })
                    except Exception as e:
                        print()
                        log(f"Erro ao ler o formato de salto no .txt: {def_salto} - {e}.")

        id_texto = f"SESSÃO {i+1:02d}"
        id_sessao(id_texto)

        # === CALCULAR A DURAÇÃO DO PRÓXIMO FILME EM SEGUNDOS ===
        duracao_proximo_seg = 0
        if i + 1 < total:
            # Pelo helper validado: se o próximo tempo vier quebrado, o filme
            # atual segue rodando sem antecipação em vez de derrubar o laço.
            proximo_seg = converter_hhmmss(tempos[i+1].split("|")[0])
            if proximo_seg is None:
                print()
                log(f"[AVISO] SESSÃO {i+1:02d}: não foi possível ler a duração do próximo "
                    f"filme ({tempos[i+1]!r}). Seguindo sem tempo de antecipação.")
            else:
                duracao_proximo_seg = proximo_seg

        if midia_decorrido_global > 0:
            print()
            log(f"Retomando a SESSÃO {i+1:02d} do segundo {int(midia_decorrido_global)}.")
        else:
            print()
            # Calcula o total efetivo respeitando encerrar_apos_filmes
            total_efetivo = global_encerrar_apos_filmes if global_encerrar_apos_filmes > 0 else total
            log(f"Filme {i+1}/{total_efetivo} - Duração sem créditos: {tempo_total}.")

        # === CARREGA AS REGRAS DE CENSURA DO FILME ATUAL ===
        lista_censuras = carregar_censuras_do_filme(i)

        # --- Reload de encerrar_apos_filmes do painel (pode ter mudado durante a live) ---
        try:
            mtempo = os.path.getmtime(painel_geral)
            if mtempo != ultima_modificacao_tempos:
                config = {}
                with open(painel_geral, "r", encoding="utf-8") as f:
                    for linha in f:
                        linha = linha.strip()
                        if linha and "=" in linha and not linha.startswith("#") and not linha.startswith("="):
                            chave, valor = linha.split("=", 1)
                            config[chave.strip()] = valor.strip()
                global_encerrar_apos_filmes = int(config.get("encerrar_apos_filmes", global_encerrar_apos_filmes))
                ultima_modificacao_tempos = mtempo
        except Exception:
            pass

        resultado = esperar(tempo_total, cena, fonte_vlc,
            is_midia=True,
            duracao_proximo_seg=duracao_proximo_seg,
            lista_saltos=lista_saltos,
            lista_censuras=lista_censuras,
            indice_filme=i)

        if resultado == "pular":
            print()
            log(f"Cena mudada manualmente. Progresso da SESSÃO {i+1:02d} salvo.")
            rotear_pulo()
            return

        if resultado == "reset_primeiro":
            print()
            log(f"Reinício geral. Voltando para a SESSÃO 01 do 0.")
            midia_idx_global = 0
            midia_decorrido_global = 0.0
            timeline_vlc_global = -1
            continue

        # === INTERCEPTAÇÃO DOS CENÁRIOS DE TRANSIÇÃO LIMPA ===
        if resultado == "pausa_quantidade":
            print()
            log(f"Quantidade de filmes atingida ({global_pausa_apos_filmes}). Pausando com 30 s de antecipação.")
            aba_pausa("quantidade")
            return

        if resultado == "pausa_oraculo":
            print()
            log("Cenário 1 ativado: o Oráculo barrou o próximo filme no minuto 1. Transição para a PAUSA aos 30 s.")
            aba_pausa()
            return

        if resultado == "pausa_horario":
            print()
            log("Cenário 2 ativado: já passou das 23 h na reta final do filme atual. Indo direto para a PAUSA.")
            aba_pausa()
            return
        
        # === Skip manual detectado. Avança o índice e segue para o próximo filme (PAUSE é independente: só por quantidade/manual). ===
        if resultado == "skip_detectado":
            print()
            log("Skip manual detectado durante a reprodução. Pulando para a próxima mídia.", toast=True)

            # Reseta as memórias de tempo para o próximo filme começar do zero absoluto
            midia_decorrido_global = 0.0
            timeline_vlc_global = -1

            time.sleep(0.5)

            midia_idx_global += 1
            print()
            log(f"Progresso atualizado. Avançando para a SESSÃO {midia_idx_global+1:02d}.")

            # --- Encerramento por quantidade de filmes (também no skip) ---
            if global_encerrar_apos_filmes > 0 and midia_idx_global == global_encerrar_apos_filmes:
                print()
                log(f"Encerramento programado atingido ({global_encerrar_apos_filmes} filmes). Indo para RAID/FINAL.", toast=True)
                visibilidade_fonte(cena, "SESSÃO ID", False)
                midia_idx_global = 0
                midia_decorrido_global = 0.0
                timeline_vlc_global = -1
                aba_raid()
                return

            if i < total - 1:
                # PAUSE independente — só quantidade/manual, não automático no skip
                pass
            else:
                visibilidade_fonte(cena, "SESSÃO ID", False)
                print()
                log("Filmes finalizados via skip. Escondendo o ID da sessão.")

            continue  # Volta ao topo do loop para o próximo filme

        # === AVANÇO AUTOMÁTICO (Só roda se o filme terminar sozinho) ===
        midia_idx_global += 1
        midia_decorrido_global = 0.0

        # --- Encerramento por quantidade de filmes (fim natural) ---
        if global_encerrar_apos_filmes > 0 and midia_idx_global == global_encerrar_apos_filmes:
            print()
            log(f"Encerramento programado atingido ({global_encerrar_apos_filmes} filmes). Indo para RAID/FINAL.", toast=True)
            visibilidade_fonte(cena, "SESSÃO ID", False)
            # Zera contadores pra não retomar errado no RAID
            midia_idx_global = 0
            midia_decorrido_global = 0.0
            timeline_vlc_global = -1
            aba_raid()  # segue o fluxo normal: RAID -> FINAL -> stop_sistema
            return

        if i < total - 1:
            skip_videos(fonte_vlc)
            time.sleep(2)

            # == Pausa Noturna no Término Normal ==
            hora_atual = int(time.strftime("%H"))
            if hora_atual >= 23 or hora_atual <= 6:
                print()
                log("Horário limite detectado no fluxo normal. Ativando a pausa noturna.")
                aba_pausa()
                return

            continue

        else:
            visibilidade_fonte(cena, "SESSÃO ID", False)
            print()
            log("Filmes finalizados normalmente. Escondendo o ID da sessão.")

    if event_client and event_client.resgate_em_andamento:
        print()
        log("Resgate da cena MÍDIAS em andamento. Segurando a cena atual.")

        while event_client.resgate_em_andamento:
            time.sleep(0.5)
        print()
        log("Todos os resgates foram concluídos.")

    # Zera para a próxima live quando tudo acabar
    midia_idx_global = 0
    aba_raid()
    return

def arquivo_tempo(caminho=None):
    if caminho is None:
        caminho = os.path.join(diretorio_base, "tempo_duracao.txt")
        
    tempos = []
    descartadas = 0
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            for numero, linha in enumerate(f, 1):
                linha = linha.strip()
                # Ignora o bloco de comentarios, igual ao Controle de Censuras e ao Painel
                if linha and not linha.startswith("#") and not linha.startswith("="):
                    # Só aceita duração válida: um texto errado no .txt é registrado
                    # e pulado, em vez de quebrar a conta do próximo filme mais adiante.
                    if converter_hhmmss(linha.split("|")[0]) is None:
                        print()
                        log(f"[AVISO] tempo_duracao.txt linha {numero} ignorada: "
                            f"duração inválida (esperado HH:MM:SS ou HH:MM:SS:MS) -> {linha!r}")
                        descartadas += 1
                        continue
                    tempos.append(linha)
    except Exception as e:
        print()
        log(f"Erro ao ler o arquivo de tempos ({caminho}): {e}")
    
    if descartadas:
        print()
        log(f"[AVISO] tempo_duracao.txt: {descartadas} linha(s) inválida(s) ignorada(s). "
            f"Confira o formato HH:MM:SS ou HH:MM:SS:MS.")
    if not tempos:
        print()
        log(f"[ERRO] tempo_duracao.txt não tem nenhum tempo válido. O sistema não pode continuar.")
    return tempos

def skip_videos(nome_fonte="FILMES"):
    client.trigger_media_input_action(
        nome_fonte,
        "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_NEXT"
    )
    print()
    log("Pulo realizado.")

def aba_pausa(modo="oraculo"):
    global midia_decorrido_global, ultima_mod_pausa, global_pausa_modo_atual, global_pausa_retorno, global_oraculo_retorno
    client.trigger_media_input_action("FILMES", "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PAUSE")
    cena = "PAUSA"
    trocar_cena(cena)
    print()
    if modo == "quantidade":
        log("Pausa por quantidade ativada. Aguardando o horário de retorno.", toast=True)
    else:
        log("Pausa noturna ativada. Aguardando até o horário permitido.", toast=True)

    chave_retorno = "pausa_retorno" if modo == "quantidade" else "oraculo_retorno"
    global_pausa_modo_atual = modo
    ultima_mod_pausa = global_pausa_retorno if modo == "quantidade" else global_oraculo_retorno
    proximo_retorno = None

    def _recalcular_retorno():
        nonlocal proximo_retorno
        retorno_str = global_pausa_retorno if modo == "quantidade" else global_oraculo_retorno
        horario_retorno = converter_hhmmss_tupla(retorno_str)
        if horario_retorno is None:
            # Antes isso falhava em silêncio: a pausa simplesmente nunca voltava.
            print()
            log(f"[AVISO] Horário de retorno ({chave_retorno}) inválido: {retorno_str!r}. "
                f"Esperado HH:MM:SS ou HH:MM:SS:MS. Esta pausa não terá retorno automático.")
            proximo_retorno = None
        else:
            h_r, m_r, s_r, _ = horario_retorno
            proximo_retorno = datetime.now().replace(hour=h_r, minute=m_r, second=s_r, microsecond=0)
            if proximo_retorno <= datetime.now():
                proximo_retorno += timedelta(days=1)

    _recalcular_retorno()

    while True:
        try:
            cena_atual = cena_ativa_obs()
            if cena_atual != cena:
                print()
                log(f"Saindo da PAUSA. Nova cena detectada: {cena_atual}.")
                global_pausa_modo_atual = None
                rotear_pulo()
                return
        except Exception as e:
            print()
            log(f"Erro ao verificar a cena durante a PAUSA: {e}.")

        # == Recalcula se o painel foi atualizado (global mudou) ==
        try:
            retorno_atual = global_pausa_retorno if modo == "quantidade" else global_oraculo_retorno
            if retorno_atual != ultima_mod_pausa:
                ultima_mod_pausa = retorno_atual
                _recalcular_retorno()
        except Exception:
            pass

        # == Auto-retorno por horário agendado ==
        if proximo_retorno and datetime.now() >= proximo_retorno:
            print()
            log("Horário de retorno atingido. Saindo da PAUSA.")
            global_pausa_modo_atual = None
            trocar_cena("MÍDIAS")
            time.sleep(0.5)
            # Busca o cursor salvo antes de reproduzir, pra evitar que o OBS reinicie do início
            if midia_decorrido_global > 0:
                client.set_media_input_cursor("FILMES", int(midia_decorrido_global * 1000))
                time.sleep(0.3)
            client.trigger_media_input_action("FILMES", "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PLAY")
            rotear_pulo()
            return

        # Vigilância: se X/Y não voltar em 60 s, força MÍDIAS
        if proximo_retorno and datetime.now() >= proximo_retorno + timedelta(seconds=TOLERANCIA_RETORNO_SEGUNDOS):
            print()
            log(f"[VIGILÂNCIA] Retorno ({chave_retorno}) não aconteceu em {TOLERANCIA_RETORNO_SEGUNDOS} s. Forçando MÍDIAS.")
            global_pausa_modo_atual = None
            trocar_cena("MÍDIAS")
            time.sleep(0.5)
            # Busca o cursor salvo antes de reproduzir, pra evitar que o OBS reinicie do início
            if midia_decorrido_global > 0:
                client.set_media_input_cursor("FILMES", int(midia_decorrido_global * 1000))
                time.sleep(0.3)
            client.trigger_media_input_action("FILMES", "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PLAY")
            rotear_pulo()
            return

        # 1s entre detecções na pausa: o usuário não está interagindo, não precisa de reflexo rápido
        time.sleep(1)

def auto_retorno_midias():
    try:
        if global_modo_conteudo == "rerun":
            log("Retorno às MÍDIAS ignorado. Modo Rerun ativo.")
            return
        # Prioridade: pausa interna (X/Y) ganha do agendado (05:00)
        if global_pausa_modo_atual is not None:
            log(f"Retorno às MÍDIAS ignorado. A pausa interna ({global_pausa_modo_atual}) tem prioridade.")
            return
        if cena_ativa_obs() == "PAUSA":
            print()
            log("Horário agendado para o retorno automático às MÍDIAS atingido. Retornando para a cena de filmes.")
            trocar_cena("MÍDIAS")
            time.sleep(0.5)
            client.trigger_media_input_action("FILMES", "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PLAY")
        else:
            print()
            log('Horário de retorno automático atingido, mas a cena atual não é "PAUSA". Nenhuma ação foi tomada.')
    except Exception as e:
        print()
        log(f"Erro ao verificar a cena para o retorno automático: {e}.")

def horario_de_rerun():
    global global_rerun_horario_final, global_rerun_dias

    inicio_linha = time.strftime("%H:%M")  # Fixo: horário em que o Rerun começou

    ultimo_horario_visto = None
    ultimos_dias_vistos = None
    momento_final = None
    segundos_totais = None
    data_formatada = ""

    while True:
        # RECONHECIMENTO EM TEMPO REAL: se mudar no TXT, o sistema recalcula na hora!
        if global_rerun_horario_final != ultimo_horario_visto or global_rerun_dias != ultimos_dias_vistos:
            ultimo_horario_visto = global_rerun_horario_final
            ultimos_dias_vistos = global_rerun_dias

            try:
                horario_rerun = converter_hhmmss_tupla(ultimo_horario_visto)
                if horario_rerun is None:
                    raise ValueError(f"horário inválido (esperado HH:MM:SS ou HH:MM:SS:MS): {ultimo_horario_visto!r}")
                h, m, s, _ = horario_rerun
                agora = datetime.now()
                momento_final = (agora + timedelta(days=ultimos_dias_vistos)).replace(hour=h, minute=m, second=s, microsecond=0)

                # Aquela correção inteligente se os dias forem 0 e o horário de hoje já passou
                if ultimos_dias_vistos == 0 and momento_final <= agora:
                    momento_final += timedelta(days=1)

                segundos_totais = int((momento_final - agora).total_seconds())
                if segundos_totais < 0:
                    segundos_totais = 0

                data_formatada = momento_final.strftime("%d/%m/%Y às %H:%M:%S")

                print()
                log(f"[ATUALIZADO] Alvo do Rerun atualizado no TXT. Novo encerramento: {data_formatada}.")
            except Exception as e:
                print()
                log(f"Erro ao processar a alteração de horário do Rerun: {e}.")

        # Verificação de término (wall clock)
        if segundos_totais is not None and segundos_totais > 0:
            agora_atual = datetime.now()
            if momento_final and momento_final <= agora_atual:
                print("\n[OK] Limite de tempo do Rerun atingido com sucesso.")
                return "finalizar"

        # Verificação de troca de cena manual no OBS
        try:
            cena_atual = cena_ativa_obs()
            if cena_atual != "MÍDIAS":
                return "pular"
        except Exception:
            pass

        # ⏳ CRONÔMETRO REGRESSIVO EM TEMPO REAL
        if segundos_totais is not None and segundos_totais > 0:
            agora_atual = datetime.now()
            restante_seg = max(0, int((momento_final - agora_atual).total_seconds()))
            
            mins, secs = divmod(restante_seg, 60)
            horas, mins = divmod(mins, 60)
            
            print(f"{inicio_linha} | Restante: {horas:02d}:{mins:02d}:{secs:02d} | Encerramento: {data_formatada}   ", end="\r", flush=True)
        
        # 1s entre atualizacoes do relogio: o display muda a cada segundo mesmo, 0.5s so repetia o valor
        time.sleep(1)

def aba_rerun():
    global global_modo_conteudo
    cena = "MÍDIAS"

    limpar_cache_vis()

    # == Ligando Fontes para o Rerun ==
    visibilidade_fonte(cena, "RERUN", True)
    visibilidade_fonte(cena, "SPOTIFY", True)
    visibilidade_fonte(cena, "MÚSICAS", True)
    visibilidade_fonte(cena, "STREAMER OFF", True)

    # == Desligando Fontes para o Rerun ==
    visibilidade_fonte(cena, "FILMES", False)
    visibilidade_fonte(cena, "SESSÃO ID", False)
    visibilidade_fonte(cena, "GIF", False)
    visibilidade_fonte(cena, "WEBCAM", False)
    visibilidade_fonte(cena, "STREAMER ON", False)
    visibilidade_fonte(cena, "CENSURA", False)
    visibilidade_fonte(cena, "TARJA", False)
    visibilidade_fonte(cena, "EV BRADESCO", False)
    visibilidade_fonte(cena, "WORD_VS", False)
    trocar_cena(cena)

    resultado = horario_de_rerun()

    if resultado == "pular":
        rotear_pulo()

        return
    
    if global_saida_rerun == "raid":
        aba_raid()

    elif global_saida_rerun == "start":
        global_modo_conteudo = global_modo_destino
        resetar_fluxo()

    else:
        aba_final()

def aba_raid():
    cena = "RAID"
    trocar_cena(cena)
    if esperar(global_duracao_raid, cena) == "pular":
        print()
        log("Cena RAID mudada manualmente.")
        rotear_pulo()
        return
    if global_modo_raid == "rerun":
        aba_rerun()
    else:
        aba_final()

def aba_final():
    cena = "FINAL"
    trocar_cena(cena)
    if esperar(global_duracao_final, cena) == "pular":
        print()
        log("Cena FINAL mudada manualmente.")
        rotear_pulo()
        return
    stop_sistema()

def _travar_painel_seguranca():
    """Reescreve o Painel de Controle: reseta campos de uso único aos padrões.
    Compartilhada entre stop_sistema() e _ao_parar() (antes era código duplicado).

    Reseta:
    - executar_sistema = no                (trava de segurança)
    - pausa_apos_filmes = 0                (pausa por quantidade)
    - encerrar_apos_filmes = 0             (encerramento por quantidade)
    - rerun_dias = 1                       (padrão do rerun)
    - rerun_horario_final = 23:59:59       (padrão seguro: fim do dia)
    - pausa_retorno = 23:59:59             (padrão seguro: fim do dia)
    - oraculo_retorno = 23:59:59           (padrão seguro: fim do dia)
    - oraculo_ativado = nao                (padrão do oráculo)

    CORREÇÃO: procura a linha pela CHAVE, não pelo texto exato do valor.
    Mantém a formatação original (espaços, EOL).
    Horários usam 23:59:59 como "desligado/seguro" — não dispara à meia-noite.
    """
    # Mapeamento: chave -> valor_padrão
    RESETS = {
        "executar_sistema": "no",
        "pausa_apos_filmes": "0",
        "encerrar_apos_filmes": "0",
        "rerun_dias": "1",
        "rerun_horario_final": "23:59:59",
        "pausa_retorno": "23:59:59",
        "oraculo_retorno": "23:59:59",
        "oraculo_ativado": "nao",
    }

    try:
        if not os.path.exists(painel_geral):
            return
        with open(painel_geral, "r", encoding="utf-8") as f:
            linhas = f.readlines()

        resetados = []
        for idx, linha in enumerate(linhas):
            chave = linha.split("=", 1)[0].strip() if "=" in linha else ""
            if chave in RESETS:
                linhas[idx] = f"{chave} = {RESETS[chave]}{linha[len(linha.rstrip()):]}"
                resetados.append(chave)

        with open(painel_geral, "w", encoding="utf-8") as f:
            f.writelines(linhas)

        for chave in resetados:
            log(f"[SEGURANÇA] {chave} reescrito para '{RESETS[chave]}' no Painel de Controle.")
    except Exception as e:
        log(f"[SEGURANÇA] Erro ao travar o painel: {e}.")


def stop_sistema():
    global encerrar_sistema, sistema_em_andamento, global_modo_sistema, _stopping_stream, global_pausa_apos_filmes

    try:
        _stopping_stream = True
        if global_modo_sistema in ["gravar", "gravação", "gravacao", "record", "teste"]:
            client.stop_record()
            print()
            log("Gravação encerrada.", toast=True)
        elif global_modo_sistema == "live":
            client.stop_stream()
            print()
            log("Transmissão encerrada.", toast=True)
        else:
            print()
            log(f"[ERRO] Modo de sistema inválido: {global_modo_sistema!r} ao parar. "
                "Parando a transmissão e a gravação por segurança.")
            for _parar in (client.stop_stream, client.stop_record):
                try:
                    _parar()
                except Exception:
                    pass
    except Exception as e:
        log(f"Erro ao parar transmissão/gravação: {e}")
    finally:
        # CORREÇÃO: antes só zerava em caso de sucesso. Se stop_stream()/stop_record()
        # falhasse, _stopping_stream ficava travado em True pro resto da sessão e
        # on_output_state_changed() nunca mais detectava queda de stream de verdade.
        _stopping_stream = False
    trocar_cena("ENTRADA")

    time.sleep(5)

    _travar_painel_seguranca()

    global_pausa_apos_filmes = 0
    sistema_em_andamento = False
    encerrar_sistema = True

def aba_geral():
    print()
    log("Controle de cenas ativado.")
    aba_entrada()

def iniciar_midias_direto():
    global global_modo_conteudo
    print()
    log(f"Gatilho de MÍDIAS acionado. Transição para o modo {global_modo_destino}.")

    global_modo_conteudo = global_modo_destino

    cena_atual = cena_ativa_obs()
    if cena_atual != "MÍDIAS":
        trocar_cena("MÍDIAS")
        time.sleep(0.5)

    if global_modo_conteudo == "rerun":
        aba_rerun()
    else:
        aba_midias()

# === Área de Agendamento ===

def verificar_agendamento():
    global ultima_modificacao, global_obs_host, global_obs_port, global_obs_password, global_modo_sistema
    global global_plataforma, global_modo_conteudo, global_modo_destino, global_modo_raid, global_saida_rerun, global_rerun_dias, global_rerun_horario_final
    global global_oraculo_ativado, global_pausa_apos_filmes, global_pausa_retorno, global_oraculo_retorno, global_encerrar_apos_filmes
    global global_duracao_entrada, global_duracao_inicio, global_duracao_raid, global_duracao_final

    try:
        modificacao_atual = os.path.getmtime(painel_geral)
        if modificacao_atual == ultima_modificacao:
            return
        print()
        log("Painel de Controle atualizado. Recarregando as tarefas e as conexões...")
        ultima_modificacao = modificacao_atual

        schedule.clear()

        config = {}
        with open(painel_geral, "r", encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                # Ignora linhas vazias, linhas decorativas de '=' e comentários com '#'
                if linha and "=" in linha and not linha.startswith("#") and not linha.startswith("="):
                    chave, valor = linha.split("=", 1) # maxsplit=1 protege se sua senha tiver '='
                    config[chave.strip()] = valor.strip()

        # == Atualiza os dados de conexão na memória ==
        global_obs_host = config.get("obs_host", "127.0.0.1")
        global_obs_port = int(config.get("obs_port", 4455))
        global_obs_password = config.get("obs_password", "")
        global_modo_sistema = config.get("modo_sistema", "live").strip().lower()
        global_plataforma = config.get("plataforma", "twitch").strip().lower()
        global_modo_conteudo = config.get("modo_conteudo", "filmes").strip().lower()
        global_modo_destino = config.get("modo_destino", "filmes").strip().lower()
        global_modo_raid = config.get("modo_raid", "final").strip().lower()
        global_saida_rerun = config.get("saida_rerun", "final").strip().lower()
        global_rerun_dias = int(config.get("rerun_dias", 1))
        global_rerun_horario_final = config.get("rerun_horario_final", "00:00:00")
        global_oraculo_ativado = config.get("oraculo_ativado", "no").strip().lower() in ["yes", "sim", "true"]
        global_pausa_apos_filmes = int(config.get("pausa_apos_filmes", 0))
        global_pausa_retorno = config.get("pausa_retorno", "05:00:00")
        global_oraculo_retorno = config.get("oraculo_retorno", "05:00:00")
        global_encerrar_apos_filmes = int(config.get("encerrar_apos_filmes", 0))
        global_duracao_entrada = config.get("duracao_entrada", "00:00:09").strip()
        global_duracao_inicio  = config.get("duracao_inicio",  "00:07:05").strip()
        global_duracao_raid    = config.get("duracao_raid",    "00:11:10").strip()
        global_duracao_final   = config.get("duracao_final",   "00:05:10").strip()

        # == Programas & Minimização (selecionados por plataforma) ==
        # CORREÇÃO: campo vazio no painel usava "00:00:00" como padrão e agendava
        # a ação pra meia-noite. Agora só agenda se o horário estiver preenchido
        # (mesma checagem que iniciar_midias já fazia, aplicada aqui também).
        if global_plataforma in ("twitch",):
            if config.get("mixitup", ""):
                schedule.every().day.at(config.get("mixitup")).do(start_mixitup)
            if config.get("chatty", ""):
                schedule.every().day.at(config.get("chatty")).do(start_chatty)
        if config.get("streamerbot", ""):
            schedule.every().day.at(config.get("streamerbot")).do(start_streamerbot)
        if config.get("obs64studio", ""):
            schedule.every().day.at(config.get("obs64studio")).do(start_obs64studio)
        if config.get("minimizar_janelas", ""):
            schedule.every().day.at(config.get("minimizar_janelas")).do(minimizar_janelas)

        # == Conexão ==
        if config.get("conectar_obs", ""):
            schedule.every().day.at(config.get("conectar_obs")).do(conectar_obs)

        # == Iniciando o Sistema ==
        if global_modo_conteudo == "estudo":
            if config.get("iniciar_midias", ""):
                schedule.every().day.at(config.get("iniciar_midias")).do(iniciar_midias_direto)
        elif config.get("start_sistema", ""):
            schedule.every().day.at(config.get("start_sistema")).do(start_sistema)
        if config.get("retornar_midias", ""):
            schedule.every().day.at(config.get("retornar_midias")).do(auto_retorno_midias)
        log("Tarefas e dados de conexão agendados com sucesso.")

    except Exception as e:
        print()
        log(f"Erro ao verificar o painel de controle: {e}.")

verificar_agendamento()  # Verifica inicialmente ao iniciar o script

def _ao_parar():
    global _stopping_stream
    print()
    log("[SISTEMA] Parando. Encerrando a transmissão.")
    try:
        if client:
            _stopping_stream = True
            # Para a gravação se estiver rodando
            try:
                client.stop_record()
                log("[SISTEMA] Gravação encerrada via stop_record().")
            except Exception as e:
                log(f"[AVISO] Falha ao parar a gravação: {e}.")
            # Para a transmissão se estiver rodando
            try:
                client.stop_stream()
                log("[SISTEMA] Transmissão encerrada via stop_stream().")
            except Exception as e:
                log(f"[AVISO] Falha ao parar a transmissão: {e}.")
            log("[SISTEMA] Comandos de parada enviados ao OBS.")
    except Exception as e:
        log(f"[ERRO] Erro ao enviar os comandos de parada: {e}.")
    finally:
        _stopping_stream = False
    try:
        if event_client:
            event_client.disconnect()
            log("[SISTEMA] Eventos desconectados.")
    except Exception as e:
        log(f"[AVISO] Erro ao desconectar os eventos: {e}.")

    _travar_painel_seguranca()

    log("[SISTEMA] Diamante Roxo encerrado. Todas as conexões foram limpas.", toast=True)

atexit.register(_ao_parar)

def _sinal_parar(_s, _f):
    log("[SINAL] SIGINT recebido (Ctrl+C). Iniciando o encerramento.")
    # Chama o handler de saída diretamente para garantir a limpeza
    try:
        _ao_parar()
    except Exception as e:
        log(f"[ERRO] Erro durante o encerramento: {e}.")
    # Força a saída após a limpeza
    sys.exit(0)

signal.signal(signal.SIGINT, _sinal_parar)

def restaurar_cena_perfil_obs():
    """Se reconectado e o OBS mudou de perfil/coleção, volta ao padrão KICK/K.S."""
    try:
        # Sempre aplica — se já estiver certo, o OBS ignora; se mudou, corrige
        try:
            client.set_current_profile("KICK")
        except Exception:
            pass
        try:
            client.set_current_scene_collection("K.S")
        except Exception:
            pass
        log("[PERFIL/CENA] Perfil KICK e coleção K.S restaurados.")
    except Exception as e:
        log(f"[AVISO] Falha ao restaurar o perfil/cena do OBS: {e}.")


# == Loop Principal ==
while not encerrar_sistema:
    verificar_agendamento()  # Verifica a cada ciclo para detectar mudanças no arquivo

    # === Reconexão automática ao OBS caso a conexão caia durante a transmissão ===
    try:
        if client is not None:
            # Testa se a conexão ainda está viva
            client.get_current_program_scene()
        elif client is None and not _reconectando_obs:
            # Tentativa de reconectar ao OBS sem enchente (só tenta se não estiver já tentando)
            _reconectando_obs = True
            try:
                import sys as _sys, io as _io
                _old_stderr = _sys.stderr
                _sys.stderr = _io.StringIO()
                try:
                    conectado = conectar_obs()
                    if conectado:
                        log("[RECONEXÃO] Reconectado ao OBS com sucesso.")
                        restaurar_cena_perfil_obs()
                        # Se havia filme em andamento, tenta restaurar a posição
                        if midia_decorrido_global > 0 and sistema_em_andamento:
                            try:
                                client.set_media_input_cursor("FILMES", int(midia_decorrido_global * 1000))
                                time.sleep(0.3)
                                client.trigger_media_input_action("FILMES", "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PLAY")
                                log(f"[RECONEXÃO] Filme retomado do segundo {int(midia_decorrido_global)}.")
                            except Exception as e:
                                log(f"[ERRO] Falha ao retomar o filme após a reconexão: {e}.")
                    else:
                        log("[RECONEXÃO] Tentativa de reconexão com o OBS falhou. Tentando novamente no próximo ciclo...")
                finally:
                    _sys.stderr = _old_stderr
            except Exception as e:
                log(f"[ERRO] Erro ao tentar reconectar ao OBS: {e}.")
            finally:
                _reconectando_obs = False
    except Exception as e:
        # Se o cliente existe mas perdeu a conexão (ex.: o OBS fechou)
        if client is not None:
            log(f"[ERRO] Conexão com o OBS perdida: {e}.")
            client = None
            event_client = None
            _reconectando_obs = False  # Permite tentar reconectar no próximo ciclo
    # ============================================================================
    
    try:
        schedule.run_pending()
    except Exception as e:
        # Um app que falhou ao abrir (permissão, caminho etc.) não pode derrubar o sistema
        log(f"[ERRO] Falha ao executar a tarefa agendada: {e}.")
        time.sleep(5)                      # Evita loop apertado se o erro se repetir
    time.sleep(ultimo_polling)             # 1 s entre ciclos para reduzir a carga na CPU
