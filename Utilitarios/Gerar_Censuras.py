# ====================================================================
# NOME   : Gerador de Censuras
# AUTOR  : CyberPhantom (C.P.)
# VERSÃO : 1.0
# FUNÇÃO : Capturar frames de cenas a censurar em filmes
# ====================================================================

import os, re, urllib.request
import keyboard

# Preencha com o caminho completo da pasta do Diamante Roxo, ex.:
#   PASTA_PRINCIPAL = r"C:\Seu\Caminho\Diamante_Roxo"
PASTA_PRINCIPAL = r"SEU_CAMINHO_DO_DIAMANTE_ROXO_AQUI"
ARQUIVO_CENSURA = os.path.join(PASTA_PRINCIPAL, "controle_censura.txt")

tempo_inicio = None
idx_filme = 0
blocos_cenas = []  # Começa vazio, mas será alimentado se você continuar um filme

def obter_tempo_mpc():
    """Conecta na API interna do MPC-BE e pega o tempo exato"""
    try:
        with urllib.request.urlopen("http://localhost:13579/variables.html", timeout=1) as resposta:
            html = resposta.read().decode('utf-8')
            match = re.search(r'id="positionstring">([^<]+)', html)
            if match:
                tempo = match.group(1).strip()
                partes = tempo.split(":")
                if len(partes) == 2:
                    return f"00:{int(partes[0]):02d}:{int(partes[1]):02d}"
                elif len(partes) == 3:
                    return f"{int(partes[0]):02d}:{int(partes[1]):02d}:{int(partes[2]):02d}"
    except Exception as e:
        print(f"\n⚠️ MPC-BE inacessível! Verifique se a Interface Web está ligada na porta 13579.")
    return None

def salvar_no_arquivo(linha_formatada):
    cabecalho_padrao = [
        "#        🚫 SISTEMA DE CENSURAS 🚫",
        "# ====================================================================",
        '# REGRAS: ("True/False > INÍCIO (HH:MM:SS) > FIM (HH:MM:SS) > CENSURA, TARJA").',
        "# SEPARADOR: Usa (;) para colocar mais do que uma censura na mesma linha.",
        "# ====================================================================",
        "",
        "# ==== Bloco de Censuras ===="
    ]
    
    linhas_dados = []
    
    # Isola apenas os dados reais se o arquivo existir
    if os.path.exists(ARQUIVO_CENSURA):
        with open(ARQUIVO_CENSURA, "r", encoding="utf-8") as f:
            for linha in f:
                l = linha.rstrip("\n")
                if "True |" in l or "False |" in l:
                    linhas_dados.append(l)

    # Garante tamanho suficiente para o filme atual
    while len(linhas_dados) < (idx_filme + 1):
        linhas_dados.append("False | ")

    # Atualiza a linha do filme atual com o acúmulo da memória
    linhas_dados[idx_filme] = linha_formatada
    
    # Grava cabeçalho + dados limpos
    conteudo_final = cabecalho_padrao + linhas_dados if 'linhas_dados' in locals() else cabecalho_padrao + linhas_dados
    with open(ARQUIVO_CENSURA, "w", encoding="utf-8") as f:
        f.write("\n".join(conteudo_final))
    
    print("\n📝 === CONTEÚDO ATUALIZADO DO SEU CONTROLE_CENSURA.TXT ===")
    for i, l in enumerate(linhas_dados):
        print(f"Filme {i+1}: {l}")
    print("=====================================================\n")

def gatilho_inicio():
    global tempo_inicio
    tempo = obter_tempo_mpc()
    if tempo:
        tempo_inicio = tempo
        print(f"⏳ [INÍCIO CAPTURADO VIA API]: {tempo_inicio} | Mova a timeline e use o atalho de FIM...")

def gatilho_fim(tipo_fonte):
    global tempo_inicio, blocos_cenas
    if not tempo_inicio:
        print("❌ Erro: Marque o INÍCIO primeiro com Ctrl+Alt+1.")
        return
        
    tempo_fim = obter_tempo_mpc()
    if not tempo_fim:
        return

    bloco = f"{tempo_inicio} > {tempo_fim} > {tipo_fonte}"
    blocos_cenas.append(bloco)
    print(f"✔ [CENA EXTRAÍDA]: {bloco}")
    
    conteudo_final = " ; ".join(blocos_cenas)
    linha_completa = f"True | {conteudo_final}"
    
    salvar_no_arquivo(linha_completa)
    tempo_inicio = None

# === 🛠️ UPGRADE 1: FUNÇÃO PARA REVERTER MÚLTIPLAS CENAS 🛠️ ===
def gatilho_reverter():
    global blocos_cenas
    if not blocos_cenas:
        print("\n❌ Nenhuma cena para reverter neste filme na sessão atual.")
        return
        
    removido = blocos_cenas.pop()
    print(f"\n↩ [REVERTIDO]: Removida a última cena com sucesso -> {removido}")
    
    if blocos_cenas:
        conteudo_final = " ; ".join(blocos_cenas)
        linha_completa = f"True | {conteudo_final}"
    else:
        linha_completa = "False | "
        
    salvar_no_arquivo(linha_completa)

# === 🛠️ UPGRADE 3: FUNÇÃO PARA CANCELAR PONTO INICIAL PENDENTE 🛠️ ===
def gatilho_cancelar_inicio():
    global tempo_inicio
    if tempo_inicio is None:
        print("\n❌ Nenhum ponto inicial ativo para cancelar.")
        return
    print(f"\n↩ [CANCELADO]: O ponto inicial {tempo_inicio} foi descartado! Pode marcar um novo início.")
    tempo_inicio = None

# --- Inicialização ---
print("💎 Motor Web API (Versão Estruturada) Ativado! 💎")

# === 🔄 UPGRADE 2: O LOOP DO LOBBY CONTINUO 🔄 ===
while True:
    # Reseta as variáveis de estado a cada retorno para o lobby
    tempo_inicio = None
    blocos_cenas = []
    
    opcao = "1"
    if os.path.exists(ARQUIVO_CENSURA):
        print("\n📅 DETECTEI UM ARQUIVO DE CENSURAS EXISTENTE:")
        print("[1] Continuar editando / Alternar entre os filmes")
        print("[2] Iniciar um NOVO DIA (Limpar censuras antigas do arquivo)")
        print("[3] Fechar o Script por completo")
        
        opcao = input("Escolha uma opção (1, 2 ou 3): ").strip()
        if opcao == "3":
            print("\nEncerrando o Gerador de Censuras. Até mais!")
            break
        if opcao == "2":
            try:
                os.remove(ARQUIVO_CENSURA)
                print("🧹 Arquivo antigo limpo! Pronto para a nova maratona.")
            except Exception as e:
                print(f"⚠️ Nota: Não consegui resetar automaticamente: {e}")

    try:
        entrada = input("\nQual o NÚMERO do filme que vai mapear ou corrigir agora? (Ex: 1, 2): ").strip()
        idx_filme = int(entrada) - 1
    except:
        print("❌ Digite um número válido para o filme!")
        continue

    # 🔄 RESGATE DE MEMÓRIA (Funciona para qualquer filme selecionado no Lobby)
    if opcao == "1" and os.path.exists(ARQUIVO_CENSURA):
        with open(ARQUIVO_CENSURA, "r", encoding="utf-8") as f:
            linhas_existentes = [l.strip() for l in f if "True |" in l or "False |" in l]
        
        if idx_filme < len(linhas_existentes):
            linha_do_filme = linhas_existentes[idx_filme]
            if linha_do_filme.startswith("True |"):
                dados_censura = linha_do_filme.replace("True |", "").strip()
                if dados_censura:
                    blocos_cenas = [b.strip() for b in dados_censura.split(";") if b.strip()]
                    print(f"\n📥 [MEMÓRIA RECUPERADA]: Carreguei {len(blocos_cenas)} censuras existentes do Filme {idx_filme + 1}!")
                    for b in blocos_cenas:
                        print(f"   -> Já na lista: {b}")

    print(f"\n🚀 Monitorando Filme {idx_filme + 1} em segundo plano...")
    print("👉 Pressione [ESC] para salvar e voltar para o Lobby de seleção de filmes.")
    
    # Registro de atalhos ativos na sessão atual
    keyboard.add_hotkey('ctrl+alt+1', gatilho_inicio)
    keyboard.add_hotkey('ctrl+alt+2', lambda: gatilho_fim("CENSURA"))
    keyboard.add_hotkey('ctrl+alt+3', lambda: gatilho_fim("TARJA"))
    keyboard.add_hotkey('ctrl+alt+4', lambda: gatilho_fim("CENSURA, TARJA"))
    keyboard.add_hotkey('ctrl+alt+5', gatilho_reverter) # Vinculação do Upgrade 1
    keyboard.add_hotkey('ctrl+alt+6', gatilho_cancelar_inicio) # INJETADO AQUI

    # Aguarda o comando de saída para o lobby
    keyboard.wait('esc')
    
    # Desvincula os atalhos antigos para não duplicar gatilhos ao mudar de filme
    keyboard.unhook_all()
    print(f"\n🔄 Sessão do Filme {idx_filme + 1} fechada. Retornando ao menu principal...")
    print("=" * 70)
