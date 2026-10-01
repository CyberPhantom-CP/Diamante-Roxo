# ====================================================================
# ====================================================================
# Diamante Roxo v5.1
# ====================================================================
# Sistema de automação para transmissão ao vivo
# Gerencia cenas, áudio, alertas e transições no OBS Studio
# ====================================================================
# Aplicativos gerenciados:
#   - OBS Studio       Transmissão e gravação de áudio/vídeo
#   - Streamer.bot     Automação de eventos, comandos e alertas
#   - Mix It Up        Chat, comandos e interatividade
#   - Chatty           Cliente de chat com moderação
#   - Kickerino        Cliente de chat da Kick
# ====================================================================
# Plataformas:
#   - Twitch  Todos os apps (Mix It Up, Chatty, Streamer.bot, OBS)
#   - Kick    Streamer.bot, Kickerino e OBS
# Modos de operação:
#   - FILMES  Reprodução de mídia com censura por tempo e saltos
#   - RERUN   Retransmissão ao vivo com contagem regressiva
#   - ESTUDO  Acionamento direto de MÍDIAS sem passa pela cena INÍCIO
# ====================================================================
# Configuração via Painel_de_Controle.txt (horários, modos, acesso OBS)
# ====================================================================
# Autor   : CyberPhantom (C.P.)
# Criado  : 24/03/2026
# Revisão : 01/10/2026
# ====================================================================

# 1) Importação de Módulos e Configuração Inicial.

print("Carregando módulos...")

# === Biblioteca Padrão ===
import atexit
import glob
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
# O script está em 'TWITCH/Script/'. Sobe um nível para 'TWITCH/' onde ficam os .txt de config.
if getattr(sys, 'frozen', False):
    pasta_sistema = os.path.dirname(sys.executable)  # Pasta 'Script' (onde está o .exe)
else:
    pasta_sistema = os.path.dirname(os.path.abspath(__file__))  # Pasta 'Script' (onde está o .py)

# Sobe um nível: de 'TWITCH/Script/' para 'TWITCH/', base para todos os arquivos do sistema
diretorio_base = os.path.dirname(pasta_sistema)

# === LOG DO SISTEMA (Fica escondido na subpasta junto com o script) ===
dia_da_sessao = time.strftime("%Y-%m-%d")
nome_ficheiro = f"relatório_{dia_da_sessao}.log"
caminho_log   = os.path.join(pasta_sistema, nome_ficheiro)

def log(msg):
    horario = time.strftime("%H:%M:%S")
    print(f"\r{horario} - {msg}")
    
    try:
        with open(caminho_log, "a", encoding="utf-8") as f:
            horario_full = time.strftime("%Y-%m-%d %H-%M-%S")
            f.write(f"{horario_full} - INFO - {msg}\n")
    except Exception as e:
        print(f"{time.strftime('%H:%M:%S')} - Erro ao gravar no log da sessão: {e}")

log("Inicializando o Diamante Roxo...")

# === Flags de Global ===
encerrar_sistema = False
sistema_em_andamento = False
sistema_autorizado = False
client = None
event_client = None

# === Rotas para os Arquivos de Controle (Pasta Pai 'TWITCH') ===
painel_geral = os.path.join(diretorio_base, "Painel_de_Controle.txt")
caminho_censura = os.path.join(diretorio_base, "controle_censura.txt")

ultima_modificacao = 0
ultimo_polling = 3  # segundos entre cada ciclo do loop principal

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
        log("[SISTEMA BLOQUEADO] Comando inválido, de negação ou incorreto no Painel de Controle.")
        log("O Diamante Roxo SÓ será iniciado se 'executar_sistema' for configurado como: yes, sim ou true.")
        print()
        log("Encerrando por medida de segurança...")
        time.sleep(2)
        exit()
except Exception as e:
    print()
    log(f"[ERRO CRÍTICO] Falha ao verificar a trava de segurança: {e}")
    log("Encerrando o sistema imediatamente por precaução.")
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
global_oraculo_ativado = False
global_pausa_apos_filmes = 0
global_pausa_retorno = "05:00:00"
global_oraculo_retorno = "05:00:00"

# === Sistema do Rerun ===
global_rerun_dias = 1
global_rerun_horario_final = "00:00:00"



_stopping_stream = False  # True enquanto stop_stream() é intencional, evita reação do on_output_state_changed



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
        # Kickerino (cliente de chat da Kick): a pasta de instalação carrega a
        # versão no nome (ex.: Kickerino_1.43_Windows), então usamos wildcard
        # para não quebrar a cada atualização do app.
        "Kickerino.exe": [
            r"%UserProfile%\Documents\Kickerino_*\Kickerino\Kickerino.exe",
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

log("Localizando softwares...")
app_obs64studio = localizar_software("obs64.exe")
app_streamerbot = localizar_software("Streamer.bot.exe")
app_mixitup = localizar_software("MixItUp.exe")
app_chatty = localizar_software("Chatty.exe")
app_kickerino = localizar_software("Kickerino.exe")

for nome, caminho in [("OBS Studio", app_obs64studio), ("Streamer.bot", app_streamerbot), ("Mix It Up", app_mixitup), ("Chatty", app_chatty), ("Kickerino", app_kickerino)]:
    if caminho:
        log(f"{nome} encontrado: {caminho}")
    else:
        log(f"[AVISO] {nome} não encontrado! A inicialização será ignorada.")

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
        log("Mix It Up já está em execução. Pulando...")
        return
    if app_mixitup:
        pasta_padrao = os.path.dirname(app_mixitup)
        subprocess.Popen(app_mixitup, cwd=pasta_padrao)
        print()
        log("Mix It Up iniciado com sucesso!")
    else:
        print()
        log("Erro: Mix It Up não encontrado.")

def start_streamerbot():
    if verificar_app_start("Streamer.bot.exe"):
        log("Streamer.bot já está em execução. Pulando...")
        return
    if app_streamerbot:
        pasta_padrao = os.path.dirname(app_streamerbot)
        subprocess.Popen(app_streamerbot, cwd=pasta_padrao)
        print()
        log("Streamer.bot iniciado com sucesso!")
    else:
        print()
        log("Erro: Streamer.bot não encontrado.")

def start_obs64studio():
    if verificar_app_start("obs64.exe"):
        log("OBS Studio já está em execução. Pulando...")
        return
    if app_obs64studio:
        pasta_padrao = os.path.dirname(app_obs64studio)
        subprocess.Popen(app_obs64studio, cwd=pasta_padrao)
        print()
        log("OBS Studio iniciado com sucesso!")
    else:
        print()
        log("Erro: OBS Studio não encontrado.")

def start_chatty():
    if verificar_app_start("Chatty.exe"):
        log("Chatty já está em execução. Pulando...")
        return
    if app_chatty:
        pasta_padrao = os.path.dirname(app_chatty)
        subprocess.Popen(app_chatty, cwd=pasta_padrao)
        print()
        log("Chatty iniciado com sucesso!")
    else:
        print()
        log("Erro: Chatty não encontrado.")

def start_kickerino():
    if verificar_app_start("Kickerino.exe"):
        log("Kickerino já está em execução. Pulando...")
        return
    if app_kickerino:
        # cwd na pasta do app: o Kickerino carrega DLLs e o kick_config.json
        # a partir do próprio diretório, então precisa ser iniciado de lá.
        pasta_padrao = os.path.dirname(app_kickerino)
        subprocess.Popen(app_kickerino, cwd=pasta_padrao)
        print()
        log("Kickerino iniciado com sucesso!")
    else:
        print()
        log("Erro: Kickerino não encontrado.")

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

    # === Kickerino ===
    try:
        Desktop(backend="uia").window(title_re="^Kickerino.*", visible_only=True).minimize()
        log("Janela do Kickerino minimizada.")
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
        log("[VOLUME] Erro: Cliente OBS não está conectado")
        return False
    
    try:

        volume_seguro = max(0.000001, min(1.5957, volume_multiplicador))
        
        # Log detalhado se houve ajuste
        if volume_seguro != volume_multiplicador:
            log(f"[VOLUME] Valor {volume_multiplicador} ajustado para intervalo seguro: {volume_seguro}")
        
        client.set_input_volume(nome_fonte, volume_seguro)
        return True
        
    except Exception as e:
        log(f"[ERRO VOLUME] Falha ao ajustar volume de '{nome_fonte}': {e}")
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

        # Descobre fontes de ambas as cenas (cacheia automaticamente)
        fontes_antigas = self._obter_fontes_cena(prev_cena)
        fontes_novas = self._obter_fontes_cena(nova_cena)

        print()
        log(f"Transição de cena detectada: '{prev_cena}' -> '{nova_cena}'")

        # Atualiza cena atual apenas após detectar/registrar a transição
        self.cena_atual = nova_cena
        self._cache_fontes_cena.clear()

        # Se existe um alerta em andamento, tratamos a transição por estado
        if self.resgate_em_andamento:
            log("Alerta ativo durante a transição! Iniciando fluxo de transição controlada...")

            with self._trans_lock:
                # Se já houver uma transição em andamento diferente, cancela-a
                if self.transicao and (self.transicao.get('origem') != prev_cena or self.transicao.get('destino') != nova_cena):
                    log("Nova transição detectada — cancelando transição anterior.")
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
            log(f"[ERRO] Falha ao processar InputVolumeMeters: {e}")

    def aplicar_acao_inicial(self):
        global client, global_modo_conteudo
        
        # CENA MÍDIAS + MODO FILME
        if self.cena_atual == "MÍDIAS" and global_modo_conteudo == "filmes":
            try:
                client.trigger_media_input_action("FILMES", "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PAUSE")
                self._midia_pausada_pelo_alerta = True
                print()
                log("Cena MÍDIAS (Filmes): Resgate detectado! Mídia pausada...")
            except Exception as e:
                print()
                log(f"Erro ao pausar mídia no OBS: {e}")
        
        # OUTRAS CENAS (Ducking universal para TODAS as fontes de áudio, exceto fontes_alertas)
        else:
            fontes_cena = self._obter_fontes_cena(self.cena_atual)
            if not fontes_cena:
                log(f"Cena {self.cena_atual}: Nenhuma fonte de áudio encontrada para ducking.")
            
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
                                log(f"[AVISO] Não foi possível obter volume em dB da fonte '{nome_fonte}'. Usando padrão 1.0")
                    
                    sucesso = ajustar_volume_seguro(nome_fonte, 0.031622)
                    
                    if sucesso:
                        print()
                        log(f"Cena {self.cena_atual}: Resgate detectado! Volume de '{nome_fonte}' reduzido para -30dB...")
                    else:
                        print()
                        log(f"Cena {self.cena_atual}: Falha ao reduzir volume de '{nome_fonte}'")
                        
                except Exception as e:
                    print()
                    log(f"Erro ao ajustar volume da fonte '{nome_fonte}' no OBS: {e}")

    def finalizar_resgate_com_seguranca(self):
        global client, global_modo_conteudo
        print()
        log("[SISTEMA] Timer de 3 segundos esgotado. Finalizando resgate com segurança!")
        
        self.resgate_em_andamento = False
        self.timer_retorno = None

        # 1⃣ COFRE DE VOLUMES (Proteção máxima contra TypeError)
        try:
            # Captura e limpa o cofre como uma operação só, protegida por lock —
            # finalizar_resgate_com_seguranca roda tanto pela thread de eventos do
            # OBS quanto disparada por threading.Timer, então sem lock dava pra
            # perder ou duplicar uma entrada se as duas caíssem ao mesmo tempo.
            with self._vol_lock:
                itens_para_restaurar = list(self.volumes_originais.items())
                self.volumes_originais.clear()

            if itens_para_restaurar:
                for fonte, vol_original in itens_para_restaurar:
                    log(f"Alerta concluído! Iniciando Fade-In para '{fonte}' voltando ao volume original...")
                    threading.Thread(target=self.executar_efeito_fade, args=(fonte, 0.031622, vol_original, 2), daemon=True).start()
            else:
                log("Nenhum volume de áudio pendente no cofre para restaurar.")
        except Exception as e:
            log(f"Erro ignorado ao tentar restaurar volumes: {e}")

        # 2⃣ RETOMADA DE MÍDIAS (Play dinâmico)
        try:
            # Delegar a retomada/limpeza de transição para o helper centralizado
            self._finalizar_transicao()
        except Exception as e:
            log(f"[TRANSIÇÃO] Erro ao finalizar transição via helper: {e}")

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
                    log("[FADE] Abortando fade após 3 falhas consecutivas")
                    break
        
        # Último chute para garantir o volume exato do final do fade
        vol_final_mul = max(0.000001, min(1.5957, vol_final_mul))
        if ajustar_volume_seguro(nome_fonte, vol_final_mul):
            print()
            log(f"Fade concluído: Volume da fonte '{nome_fonte}' restaurado com sucesso!")
        else:
            print()
            log(f"Erro ao finalizar fade na fonte '{nome_fonte}'")

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
            log(f"[TRANSIÇÃO] Modo FILMES: Pausada mídia 'FILMES' durante transição {origem}->{destino}.")
        except Exception as e:
            log(f"[TRANSIÇÃO] Falha ao pausar mídia na transição: {e}")

    def _aplicar_transicao_rerun(self, fontes_antigas, fontes_novas):
        """Ações imediatas ao transitarmos enquanto há alerta no modo RERUN."""
        # Em RERUN não pausamos mídia (não há vídeo reproduzindo). Apenas fazemos fade-out
        # das fontes de áudio que acabaram de entrar na cena, para evitar pico de volume.
        # Faz fade-out de TODA fonte que entrou na nova cena (não estava na anterior)
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
                log(f"[TRANSIÇÃO] Modo RERUN: iniciado fade-out de '{fonte}' (nova na cena).")
            except Exception as e:
                log(f"[TRANSIÇÃO] Falha ao aplicar fade-out em '{fonte}': {e}")

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
            log(f"[TRANSIÇÃO] Finalizando transição #{trans.get('id')}: {trans.get('origem')} -> {trans.get('destino')}")

        try:
            # Retomar FILMES se foi pausado pelo alerta e estamos na cena MÍDIAS
            if self._midia_pausada_pelo_alerta:
                if global_modo_conteudo == 'filmes' and self.cena_atual == 'MÍDIAS':
                    try:
                        client.trigger_media_input_action('FILMES', 'OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PLAY')
                        log("[TRANSIÇÃO] Mídia 'FILMES' retomada após fim do alerta.")
                    except Exception as e:
                        log(f"[TRANSIÇÃO] Erro ao retomar mídia 'FILMES': {e}")
                self._midia_pausada_pelo_alerta = False

        except Exception as e:
            log(f"[TRANSIÇÃO] Erro ao finalizar transição: {e}")

    def on_input_mute_state_changed(self, data):
        try:
            if data.input_name in self.fontes_alertas:
                if data.input_muted:
                    print()
                    log(f"[GRAMPEADOR] '{data.input_name}' MUTADO (Barra Cinza). Parando loops...")
                    self.mixer_mutado = True
                    
                    if self.resgate_em_andamento:
                        if self.timer_retorno:
                            self.timer_retorno.cancel()
                            self.timer_retorno = None
                            
                        self.finalizar_resgate_com_seguranca()
                        self.resgate_em_andamento = False
                else:
                    print()
                    log(f"[GRAMPEADOR] '{data.input_name}' DESMUTADO (Barra Verde). Sensores reativados.")
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
                log("[OBS] Stream caiu! Pausando filme...")
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
            log("[OBS] Stream estável há 3s. Retomando filme...")
            retomar_filme_se_pausado()

# === Conecta ao OBS via WebSocket ===

def conectar_obs():
    global client, event_client, global_obs_host, global_obs_port, global_obs_password
    
    if client is not None:
        print()
        log("Conexão OBS já estabelecida. Mantendo conexão atual para evitar duplicidade.")
        return True
    
    try:
        client = ReqClient(host= global_obs_host,
                           port=global_obs_port,
                           password=global_obs_password)
        print()
        log(f"Conectado ao OBS com sucesso em {global_obs_host}:{global_obs_port}!")

        event_client = GrampeadoOBS(host=global_obs_host,
                                    port=global_obs_port,
                                    password=global_obs_password)
        
        return True
    
    except Exception as e:
        print()
        log(f"Falha ao conectar no OBS ({global_obs_host}): {e}")
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
    h, m, s = map(int, tempo_str.split(":"))
    total_segundos = (h*3600 + m*60 + s)
    print()
    log(f"Aguardando {tempo_str}...")
    return esperar_com_deteccao(total_segundos, cena_esperada, nome_fonte, is_midia, duracao_proximo_seg, lista_saltos, lista_censuras, indice_filme)

def start_sistema():
    global client, sistema_em_andamento, global_modo_sistema, global_modo_conteudo

    if sistema_em_andamento:
        print()
        log("Sistema já está em andamento. Pulando início.")
        return

    if client is None:
        if not conectar_obs():
            print()
            log("ERRO: Não foi possível conectar ao OBS no horário definido.")
            return

    # Inicia transmissão/gravação no OBS
    if global_modo_sistema in ["gravar", "gravação", "record", "teste"]:
        client.start_record()
        print()
        log("Gravação sendo iniciada!")
    else:
        client.start_stream()
        print()
        log("Transmissão sendo iniciada!")

    # Inicia o fluxo: id_live, thread de cenas, e começa pela ENTRADA (9s)
    iniciar_fluxo()

def iniciar_fluxo():
    global sistema_em_andamento, global_modo_conteudo

    if global_modo_conteudo == "rerun":
        id_live("RERUN")
    else:
        id_live("REACT")

    sistema_em_andamento = True
    threading.Thread(target=aba_geral, daemon=True).start()

def resetar_fluxo():
    print()
    log("Resetando fluxo para o início...")

    iniciar_fluxo()

# === Controle de Cenas/Fontes ===

def trocar_cena(nome):
    client.set_current_program_scene(nome)
    print()
    log(f"Cena trocada para: {nome}")

def cena_ativa_obs():
    return client.get_current_program_scene().current_program_scene_name

# == Estado global de reprodução de mídia (índice, tempo decorrido, detecção de skip) ==
midia_idx_global = 0
midia_decorrido_global = 0.0
timeline_vlc_global = -1

# === SISTEMA DE CENSURA DINÂMICA ===
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
                    if ">" in bloco:
                        definicoes = bloco.split(">")
                        if len(definicoes) == 3:
                            h_i, m_i, s_i = map(int, definicoes[0].strip().split(":"))
                            h_f, m_f, s_f = map(int, definicoes[1].strip().split(":"))
                        
                            # Suporta múltiplas fontes separadas por vírgula
                            fontes_raw = definicoes[2].strip()
                            # Divide pelas vírgulas se houver, senão pega apenas o nome único
                            lista_fontes = [f.strip() for f in fontes_raw.split(",")]
                        
                            for fonte in lista_fontes:
                                lista_censuras.append({
                                    "inicio": h_i * 3600 + m_i * 60 + s_i,
                                    "fim": h_f * 3600 + m_f * 60 + s_f,
                                    "fonte": fonte,
                                    "ativo_agora": False
                                })
    except Exception as e:
        print()
        log(f"Erro ao processar censura no Filme {indice_filme + 1}: {e}")
        
    return lista_censuras

def esperar_com_deteccao(segundos, cena_esperada, nome_fonte=None, is_midia=False, duracao_proximo_seg=0, lista_saltos=None, lista_censuras=None, indice_filme=0):
    global midia_decorrido_global, timeline_vlc_global, global_oraculo_ativado, global_pausa_apos_filmes
    decorrido_total = midia_decorrido_global if is_midia else 0.0
    inicio = time.time()
    inicio_linha = time.strftime("%H:%M")  # Fixo: horario que esta secao comecou
    
    if is_midia:
        timeline_vlc_global = -1
    
    proximo_recusado = False  
    resultado_final = "normal"

    while True:
        agora = time.time()

        if is_midia and nome_fonte:
            try:
                status_obs = client.get_media_input_status(nome_fonte)
                cursor_atual = status_obs.media_cursor
                decorrido = cursor_atual / 1000.0

                if decorrido_total > 0 and decorrido < decorrido_total - 5:
                    try:
                        client.set_media_input_cursor(nome_fonte, int(decorrido_total * 1000))
                    except Exception:
                        pass
                    decorrido = decorrido_total

                if timeline_vlc_global >= 0:
                    if cursor_atual < (timeline_vlc_global - 15000):
                        if timeline_vlc_global > 5000:
                            timeline_vlc_global = cursor_atual
                            if is_midia: midia_decorrido_global = 0.0
                            resultado_final = "skip_detectado"
                            break 
                
                timeline_vlc_global = cursor_atual
            except Exception:
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

        if is_midia and lista_saltos:
            for salto in lista_saltos:
                if not salto["feito"] and decorrido >= salto["gatilho"]:
                    try:
                        ms_destino = salto["destino"] * 1000
                        client.set_media_input_cursor(nome_fonte, ms_destino)
                        print()
                        log(f"Pós-crédito detectado! Saltando para: {salto['destino']}s")
                        
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

        mins, secs = divmod(restante, 60)
        horas, mins = divmod(mins, 60)
        agora_dt = datetime.now()
        fim_dt = agora_dt + timedelta(seconds=restante)
        fim_str = fim_dt.strftime("%H:%M")
        estado = "Pausado" if (event_client and event_client.resgate_em_andamento) else "Rodando"
        corte = "Sim" if proximo_recusado else "Nao"
        print(f"{inicio_linha} | Restante: {horas:02d}:{mins:02d}:{secs:02d} | Corte: {corte} | {estado} | Fim: {fim_str}               ", end="\r")
        
        try:
            if cena_ativa_obs() != cena_esperada:
                if is_midia:
                    midia_decorrido_global = decorrido
                resultado_final = "pular"
                break
        except Exception:
            pass
        
        # 1.0s entre deteccoes: metade das chamadas ao OBS por hora de filme,
        # sem atrasar deteccao de skip/censura (o trigger e abrupto, pega na proxima)
        time.sleep(1.0)

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
                    
    return resultado_final

def rotear_pulo():
    global event_client
    nova_cena = cena_ativa_obs()
    print()
    log(f"Roteamento: Iniciando cronômetro da cena '{nova_cena}'")

    # Segurança: se a cena de destino é RAID ou FINAL, aguarda alertas terminarem
    # para não interromper o resgate com uma troca de cena brusca.
    if nova_cena in ("RAID", "FINAL"):
        if event_client and event_client.resgate_em_andamento:
            log(f"[SEGURANÇA] Alerta ativo durante roteamento para '{nova_cena}'. Aguardando...")
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
    if esperar("00:00:09", cena) == "pular":
        print()
        log("Cena ENTRADA mudada manualmente.")
        rotear_pulo()
        return
    aba_inicio()

def aba_inicio():
    cena = "INÍCIO"
    trocar_cena(cena)
    if esperar("00:07:05", cena) == "pular":
        print()
        log("Cena INÍCIO mudada manualmente.")
        rotear_pulo()
        return
    if global_modo_conteudo == "rerun":
        aba_rerun()
    else:
        aba_midias()

_vis_cache = {}

def limpar_cache_vis():
    _vis_cache.clear()

def visibilidade_fonte(cena, nome_fonte, visivel):
    try:
        if cena not in _vis_cache:
            itens = client.get_scene_item_list(cena).scene_items
            _vis_cache[cena] = itens
        else:
            itens = _vis_cache[cena]
        for item in itens:
            if item['sourceName'] == nome_fonte:
                client.set_scene_item_enabled(cena, item['sceneItemId'], visivel)
                print()
                log(f"Fonte '{nome_fonte}' -> {'LIGADA' if visivel else 'DESLIGADA'}")
                return
            if item.get('isGroup', False) or item.get('is_group', False):
                g_nome = item['sourceName']
                res_g = client.get_group_scene_item_list(g_nome).scene_items
                for sub in res_g:
                    if sub['sourceName'] == nome_fonte:
                        client.set_scene_item_enabled(g_nome, sub['sceneItemId'], visivel)
                        print()
                        log(f"Fonte '{nome_fonte}' (dentro de '{g_nome}') -> {'LIGADA' if visivel else 'DESLIGADA'}")
                        return
    except Exception as e:
        print()
        log(f"Erro ao alterar visibilidade de '{nome_fonte}': {e}")

def id_sessao(novo_texto):
    try:
        nome_fonte = "SESSÃO ID"

        client.set_input_settings(nome_fonte, {'text': novo_texto}, True)
        print()
        log(f"Sucesso: {nome_fonte} atualizada para {novo_texto}")

    except Exception as e:
        print()
        log(f"Erro ao atualizar {nome_fonte}: {e}")

def id_live(texto_aviso):
    try:
        nome_fonte = "ID LIVE"

        client.set_input_settings(nome_fonte, {'text': texto_aviso}, True)
        print()
        log(f"ID LIVE atualizado para: {texto_aviso}")

    except Exception as e:
        print()
        log(f"Erro ao atualizar {nome_fonte}: {e}")

def aba_midias():
    global midia_idx_global, midia_decorrido_global, timeline_vlc_global, event_client
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
                        # Extrai a hora de Gatilho
                        h_g, m_g, s_g = map(int, s[0].strip().split(":"))
                        # Extrai a hora de Destino
                        h_d, m_d, s_d = map(int, s[1].strip().split(":"))
                        
                        # Alimenta a lista de saltos do pacote novo
                        lista_saltos.append({
                            "gatilho": h_g*3600 + m_g*60 + s_g, 
                            "destino": h_d*3600 + m_d*60 + s_d, 
                            "feito": False
                        })
                    except Exception as e:
                        print()
                        log(f"Erro ao ler formato de salto no .txt: {def_salto} - {e}")

        id_texto = f"SESSÃO {i+1:02d}"
        id_sessao(id_texto)

        # === CALCULAR A DURAÇÃO DO PRÓXIMO FILME EM SEGUNDOS ===
        duracao_proximo_seg = 0
        if i + 1 < total:  
            linha_proximo = tempos[i+1].split("|")[0].strip()
            h_p, m_p, s_p = map(int, linha_proximo.split(":"))
            duracao_proximo_seg = h_p * 3600 + m_p * 60 + s_p

        if midia_decorrido_global > 0:
            print()
            log(f"Retomando SESSÃO {i+1:02d} do segundo {int(midia_decorrido_global)}...")
        else:
            print()
            log(f"Filme {i+1}/{total} - Duração sem créditos: {tempo_total}")

        # === CARREGA AS REGRAS DE CENSURA DO FILME ATUAL ===
        lista_censuras = carregar_censuras_do_filme(i)

        resultado = esperar(tempo_total, cena, fonte_vlc,
            is_midia=True,
            duracao_proximo_seg=duracao_proximo_seg,
            lista_saltos=lista_saltos,
            lista_censuras=lista_censuras,
            indice_filme=i)

        if resultado == "pular":
            print()
            log(f"Cena mudada manualmente. Progresso da SESSÃO {i+1:02d} salvo!")
            rotear_pulo()
            return
        
        # === INTERCEPTAÇÃO DOS CENÁRIOS DE TRANSIÇÃO LIMPA ===
        if resultado == "pausa_quantidade":
            print()
            log(f"Quantidade de filmes atingida ({global_pausa_apos_filmes}). Pausando com 30s de antecipação.")
            aba_pausa("quantidade")
            return

        if resultado == "pausa_oraculo":
            print()
            log("Cenário 1 Ativado: O Oráculo barrou o próximo filme no minuto 1. Transição para PAUSA aos 30s.")
            aba_pausa()
            return
            
        if resultado == "pausa_horario":
            print()
            log("Cenário 2 Ativado: Já passou das 23h na reta final do filme atual! Indo direto para a PAUSA.")
            aba_pausa()
            return
        
        # === Skip manual detectado. Avança o índice e, se for entre 23h-06h, ativa pausa noturna. ===
        if resultado == "skip_detectado":
            print()
            log("Skip manual detectado durante a reprodução. Pulando para próxima mídia...")

            # Reseta as memórias de tempo para o próximo filme começar do zero absoluto
            midia_decorrido_global = 0.0
            timeline_vlc_global = -1
            
            time.sleep(2)

            midia_idx_global += 1
            print()
            log(f"Cofre atualizado com sucesso: Avançando para SESSÃO {midia_idx_global+1:02d}.")

            if i < total - 1:
                # == Pausa Noturna no Skip Manual ==
                hora_atual = int(time.strftime("%H"))
                if hora_atual >= 23 or hora_atual <= 6:
                    print()
                    log("Horário limite detectado no skip manual. Ativando pausa noturna.")
                    aba_pausa()
                    return
            else:
                visibilidade_fonte(cena, "SESSÃO ID", False)
                print()
                log("Filmes finalizados via skip. Escondendo ID da Sessão.")
            
            continue  # Volta ao topo do loop para o próximo filme

        # === AVANÇO AUTOMÁTICO (Só roda se o filme terminar sozinho) ===
        midia_idx_global += 1
        midia_decorrido_global = 0.0

        if i < total - 1:
            skip_videos(fonte_vlc)
            time.sleep(2)

            # == Pausa Noturna no Término Normal ==
            hora_atual = int(time.strftime("%H"))
            if hora_atual >= 23 or hora_atual <= 6:
                print()
                log("Horário limite detectado no fluxo normal. Ativando pausa noturna.")
                aba_pausa()
                return

            continue

        else:
            visibilidade_fonte(cena, "SESSÃO ID", False)
            print()
            log("Filmes finalizados normalmente. Escondendo ID da Sessão.")

    if event_client and event_client.resgate_em_andamento:
        print()
        log("Resgate de cena MÍDIAS em andamento. Segurando cena atual...")

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
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if linha:
                    tempos.append(linha)
    except Exception as e:
        print()
        log(f"Erro ao ler o arquivo de tempos ({caminho}): {e}")
    return tempos

def skip_videos(nome_fonte="FILMES"):
    client.trigger_media_input_action(
        nome_fonte,
        "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_NEXT"
    )
    print()
    log("Skip realizado!")

def aba_pausa(modo="oraculo"):
    global midia_decorrido_global
    client.trigger_media_input_action("FILMES", "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PAUSE")
    cena = "PAUSA"
    trocar_cena(cena)
    print()
    if modo == "quantidade":
        log("Pausa por quantidade ativada. Aguardando horário de retorno...")
    else:
        log("Pausa Noturna ativada. Aguardando até o horário permitido...")

    chave_retorno = "pausa_retorno" if modo == "quantidade" else "oraculo_retorno"
    ultima_mod_pausa = 0
    proximo_retorno = None

    def _recalcular_retorno():
        nonlocal proximo_retorno
        retorno_str = "05:00:00"
        if os.path.exists(painel_geral):
            with open(painel_geral, "r", encoding="utf-8") as f:
                for linha in f:
                    if linha.strip().startswith(chave_retorno):
                        partes = linha.split("=", 1)
                        if len(partes) == 2:
                            retorno_str = partes[1].strip()
                            break
        try:
            h_r, m_r, s_r = map(int, retorno_str.split(":"))
            proximo_retorno = datetime.now().replace(hour=h_r, minute=m_r, second=s_r, microsecond=0)
            if proximo_retorno <= datetime.now():
                proximo_retorno += timedelta(days=1)
        except Exception:
            proximo_retorno = None

    _recalcular_retorno()

    while True:
        try:
            cena_atual = cena_ativa_obs()
            if cena_atual != cena:
                print()
                log(f"Saindo da PAUSA. Nova cena detectada: {cena_atual}")
                rotear_pulo()
                return
        except Exception as e:
            print()
            log(f"Erro ao verificar cena durante PAUSA: {e}")

        # == Recalcula se o painel foi editado durante a pausa ==
        try:
            mod_atual = os.path.getmtime(painel_geral)
            if mod_atual != ultima_mod_pausa:
                ultima_mod_pausa = mod_atual
                _recalcular_retorno()
        except Exception:
            pass

        # == Auto-retorno por horário agendado ==
        if proximo_retorno and datetime.now() >= proximo_retorno:
            print()
            log("Horário de retorno atingido. Saindo da PAUSA.")
            trocar_cena("MÍDIAS")
            time.sleep(0.5)
            # Busca o cursor salvo antes de reproduzir, pra evitar que o OBS reinicie do início
            if midia_decorrido_global > 0:
                client.set_media_input_cursor("FILMES", int(midia_decorrido_global * 1000))
                time.sleep(0.3)
            client.trigger_media_input_action("FILMES", "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PLAY")
            rotear_pulo()
            return

        # 3s entre deteccoes na pausa: o usuario nao esta interagindo, nao precisa de reflexo rapido
        time.sleep(3)

def auto_retorno_midias():
    try:
        if global_modo_conteudo == "rerun":
            log("retornar_midias ignorado — modo RERUN ativo")
            return
        if cena_ativa_obs() == "PAUSA":
            print()
            log("Horário agendado para retorno automático às MÍDIAS atingido. Retornando para a cena de filmes...")
            trocar_cena("MÍDIAS")
            time.sleep(0.5)
            client.trigger_media_input_action("FILMES", "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_PLAY")
        else:
            print()
            log('Horário de retorno automático atingido, mas a cena atual não é "PAUSA". Nenhuma ação tomada.')
    except Exception as e:
        print()
        log(f"Erro ao verificar cena para retorno automático: {e}")

def horario_de_rerun():
    global global_rerun_horario_final, global_rerun_dias

    inicio_linha = time.strftime("%H:%M")  # Fixo: horario que o RERUN comecou
    
    ultimo_horario_visto = None
    ultimos_dias_vistos = None
    momento_final = None
    segundos_totais = None
    data_formatada = ""

    while True:
        # RECONHECIMENTO EM TEMPO REAL: Se mudar no TXT, o sistema recalcula na hora!
        if global_rerun_horario_final != ultimo_horario_visto or global_rerun_dias != ultimos_dias_vistos:
            ultimo_horario_visto = global_rerun_horario_final
            ultimos_dias_vistos = global_rerun_dias
            
            try:
                h, m, s = map(int, ultimo_horario_visto.split(":"))
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
                log(f"[ATUALIZADO] Alvo do Rerun atualizado no TXT! Novo encerramento: {data_formatada}")
            except Exception as e:
                print()
                log(f"Erro ao processar alteração de horário do Rerun: {e}")
                continue

        # Verificação de término (wall clock)
        if segundos_totais is not None and segundos_totais > 0:
            agora_atual = datetime.now()
            if momento_final and momento_final <= agora_atual:
                print("\n[OK] Tempo limite do RERUN atingido com sucesso.")
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
            
            print(f"{inicio_linha} | Restante: {horas:02d}:{mins:02d}:{secs:02d} | Encerramento: {data_formatada}               ", end="\r")
        
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
    if esperar("00:11:10", cena) == "pular":
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
    if esperar("00:05:10", cena) == "pular":
        print()
        log("Cena FINAL mudada manualmente.")
        rotear_pulo()
        return
    stop_sistema()

def _travar_painel_seguranca():
    """Reescreve o Painel de Controle: executar_sistema -> no, pausa_apos_filmes -> 0.
    Compartilhada entre stop_sistema() e _ao_parar() (antes era código duplicado).

    CORREÇÃO 1: a versão antiga fazia conteudo.replace("executar_sistema = yes", ...),
    que só bate se o valor original for exatamente "yes" com um espaço de cada lado.
    Como a leitura da trava aceita "sim"/"true" e qualquer espaçamento/maiúscula,
    quem usasse "sim" ou "true" via o log dizer "trava ativada" sem a trava ter sido
    reescrita de verdade. Agora procura a linha pela CHAVE (como já era feito pra
    pausa_apos_filmes), não pelo texto exato do valor.
    CORREÇÃO 2: stop_sistema() chamava isso sem try/except (só _ao_parar() tinha).
    Se o arquivo estivesse bloqueado/ausente nesse instante, a thread do fluxo de
    cenas morria calada. Agora as duas chamam esta função, que já tem o try/except.
    """
    try:
        if not os.path.exists(painel_geral):
            return
        with open(painel_geral, "r", encoding="utf-8") as f:
            linhas = f.readlines()

        for idx, linha in enumerate(linhas):
            chave = linha.split("=", 1)[0].strip() if "=" in linha else ""
            if chave == "executar_sistema":
                linhas[idx] = f"executar_sistema = no{linha[len(linha.rstrip()):]}"
            elif linha.strip().startswith("pausa_apos_filmes"):
                linhas[idx] = f"pausa_apos_filmes = 0{linha[len(linha.rstrip()):]}"

        with open(painel_geral, "w", encoding="utf-8") as f:
            f.writelines(linhas)

        log("[SEGURANCA] executar_sistema reescrito para 'no' no Painel de Controle.")
        log("[SEGURANCA] pausa_apos_filmes reescrito para 0 no Painel de Controle.")
    except Exception as e:
        log(f"[SEGURANCA] Erro ao travar painel: {e}")


def stop_sistema():
    global encerrar_sistema, sistema_em_andamento, global_modo_sistema, _stopping_stream, global_pausa_apos_filmes

    try:
        _stopping_stream = True
        if global_modo_sistema in ["gravar", "gravação", "record", "teste"]:
            client.stop_record()
            print()
            log("Gravação encerrada!")
        else:
            client.stop_stream()
            print()
            log("Transmissão encerrada!")
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
    log("Controle de Cenas foi ativado!")
    aba_entrada()

def iniciar_midias_direto():
    global global_modo_conteudo
    print()
    log(f"Gatilho de MÍDIAS acionado! Transição para modo {global_modo_destino}...")

    global_modo_conteudo = global_modo_destino

    if global_modo_conteudo == "rerun":
        id_live("RERUN")
    else:
        id_live("REACT")

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
    global global_oraculo_ativado, global_pausa_apos_filmes, global_pausa_retorno, global_oraculo_retorno

    try:
        modificacao_atual = os.path.getmtime(painel_geral)
        if modificacao_atual == ultima_modificacao:
            return
        print()
        log("Painel de Controle atualizado! Recarregando tarefas e conexões...")
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

        # == Programas & Minimização (selecionados por plataforma) ==
        # CORREÇÃO: campo vazio no painel usava "00:00:00" como padrão e agendava
        # a ação pra meia-noite. Agora só agenda se o horário estiver preenchido
        # (mesma checagem que iniciar_midias já fazia, aplicada aqui também).
        if global_plataforma in ("twitch",):
            if config.get("mixitup", ""):
                schedule.every().day.at(config.get("mixitup")).do(start_mixitup)
            if config.get("chatty", ""):
                schedule.every().day.at(config.get("chatty")).do(start_chatty)
        if global_plataforma in ("kick",):
            # Kickerino é o cliente de chat da Kick (equivalente ao Chatty do Twitch).
            if config.get("kickerino", ""):
                schedule.every().day.at(config.get("kickerino")).do(start_kickerino)
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
        log(f"Erro ao verificar painel de controle: {e}")

verificar_agendamento()  # Verifica inicialmente ao iniciar o script

def _ao_parar():
    global _stopping_stream
    print()
    log("[SISTEMA] Parando... encerrando transmissao.")
    try:
        if client:
            _stopping_stream = True
            client.stop_stream()
            client.stop_record()
            log("[SISTEMA] Transmissao encerrada.")
    except Exception:
        pass
    finally:
        _stopping_stream = False
    try:
        if event_client:
            event_client.disconnect()
            log("[SISTEMA] Eventos desconectados.")
    except Exception:
        pass

    _travar_painel_seguranca()

    log("[SISTEMA] Diamante Roxo encerrado. Todas as conexoes foram limpas.")

atexit.register(_ao_parar)

def _sinal_parar(_s, _f):
    sys.exit(0)

signal.signal(signal.SIGINT, _sinal_parar)

# == Loop Principal ==
while not encerrar_sistema:
    verificar_agendamento()  # Verifica a cada ciclo para detectar mudanças no arquivo
    
    try:
        schedule.run_pending()
    except Exception as e:
        # Um app que falhou ao abrir (permissao, caminho, etc) nao pode derrubar o sistema
        log(f"[ERRO] Falha ao executar tarefa agendada: {e}")
        time.sleep(5)                      # Evita loop apertado se o erro se repetir
    time.sleep(ultimo_polling)             # 3s entre ciclos para reduzir carga na CPU
