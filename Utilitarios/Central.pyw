import ctypes
import os
import re
import sys
import customtkinter as ctk

ctk.set_appearance_mode("dark")

TITULO_JANELA = "Central — Diamante Roxo"
NOME_MUTEX = "Central_DiamanteRoxo_GUI"
_handle_mutex = None

PASTA_PADRAO = os.path.dirname(os.path.abspath(__file__))
CAMINHO_PAINEL = os.path.join(PASTA_PADRAO, "Painel_de_Controle.txt")
if len(sys.argv) > 1:
    CAMINHO_PAINEL = os.path.abspath(sys.argv[1])

PADRAO_TEMPO = re.compile(r"^\d{2}:\d{2}:\d{2}$")

OPCOES = {
    "modo_sistema": ["live", "gravar", "teste"],
    "plataforma": ["twitch", "kick"],
    "modo_conteudo": ["filmes", "rerun", "estudo"],
    "modo_destino": ["filmes", "rerun"],
    "modo_raid": ["final", "rerun"],
    "saida_rerun": ["final", "raid", "start"],
    "executar_sistema": ["yes", "no"],
    "oraculo_ativado": ["yes", "no"],
}

CAMPOS = [
    ("Modo", "modo_sistema", "Modo do sistema", "enum"),
    ("Modo", "plataforma", "Plataforma", "enum"),
    ("Modo", "modo_conteudo", "Conteudo", "enum"),
    ("Modo", "modo_destino", "Destino (modo estudo)", "enum"),
    ("Modo", "modo_raid", "Cena apos alerta RAID", "enum"),
    ("Modo", "saida_rerun", "Saida do rerun", "enum"),
    ("Modo", "rerun_dias", "Dias do rerun", "int"),
    ("Modo", "rerun_horario_final", "Horario final do rerun", "tempo"),
    ("Pausa", "oraculo_ativado", "Oraculo (corte apos 23h)", "bool"),
    ("Pausa", "pausa_apos_filmes", "Pausa apos N filmes (0 = off)", "int"),
    ("Pausa", "pausa_retorno", "Retorno da pausa", "tempo"),
    ("Pausa", "oraculo_retorno", "Retorno do oraculo", "tempo"),
    ("OBS", "obs_host", "Host", "host"),
    ("OBS", "obs_port", "Porta", "port"),
    ("OBS", "obs_password", "Senha", "senha"),
    ("Agendamentos", "conectar_obs", "Conectar OBS", "tempo"),
    ("Agendamentos", "start_sistema", "Iniciar sistema", "tempo"),
    ("Agendamentos", "retornar_midias", "Retornar midias", "tempo"),
    ("Agendamentos", "iniciar_midias", "Iniciar midias (modo estudo)", "tempo"),
    ("Agendamentos", "mixitup", "MixItUp", "tempo"),
    ("Agendamentos", "streamerbot", "Streamer.bot", "tempo"),
    ("Agendamentos", "kickerino", "Kickerino", "tempo"),
    ("Agendamentos", "chatty", "Chatty", "tempo"),
    ("Agendamentos", "obs64studio", "OBS 64 Studio", "tempo"),
    ("Agendamentos", "minimizar_janelas", "Minimizar janelas", "tempo"),
]

COR_FUNDO_INVALIDA = "#5a1b1b"
COR_FUNDO_PADRAO_ENTRY = "#343638"
COR_OK = "#6ab04c"
COR_AVISO = "#f0932b"
COR_ERRO = "#eb4d4b"
COR_NEUTRA = "#a0a0a0"


def validar(tipo, texto):
    valor = texto.strip()
    if tipo == "tempo":
        if not PADRAO_TEMPO.match(valor):
            return False
        h, m, s = (int(p) for p in valor.split(":"))
        return 0 <= h < 24 and 0 <= m < 60 and 0 <= s < 60
    if tipo == "int":
        return valor.isdigit()
    if tipo == "port":
        return valor.isdigit() and 1 <= int(valor) <= 65535
    if tipo == "host":
        return bool(valor) and not any(c.isspace() for c in valor) and not valor.startswith(("#", "="))
    if tipo == "senha":
        return "\n" not in texto and not valor.startswith(("#", "="))
    return True


def _validar_enum(chave, texto):
    return texto.strip() in OPCOES.get(chave, [texto.strip()])


def _canonizar(chave, valor):
    v = valor.lower()
    if chave in ("executar_sistema", "oraculo_ativado"):
        return "yes" if v in ("yes", "sim", "true") else "no"
    if chave == "modo_sistema" and v in ("record", "gravacao"):
        return "gravar"
    return valor


def ler_painel(caminho):
    dados = {}
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            for linha in f:
                sem = linha.strip()
                if "=" in sem and not sem.startswith(("#", "=")):
                    chave, valor = sem.split("=", 1)
                    valor = valor.split("#", 1)[0].strip()
                    dados[chave.strip()] = valor
    except OSError:
        pass
    return dados


def gravar_chave(caminho, chave, valor):
    try:
        with open(caminho, "r", encoding="utf-8", newline="") as f:
            conteudo = f.read()
    except OSError:
        conteudo = ""
    eol = "\r\n" if "\r\n" in conteudo else "\n"
    linhas = conteudo.splitlines(keepends=True)
    achou = False
    for i, linha in enumerate(linhas):
        texto = linha.rstrip("\r\n")
        sem = texto.strip()
        if "=" in sem and not sem.startswith(("#", "=")):
            k, _ = sem.split("=", 1)
            if k.strip() == chave:
                idx = texto.index("=")
                linhas[i] = texto[:idx] + "= " + valor + eol
                achou = True
                break
    if not achou:
        linhas.append(chave + " = " + valor + eol)
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.writelines(linhas)
    os.replace(tmp, caminho)
    return os.path.getmtime(caminho)


class CentralApp:
    def __init__(self, raiz):
        self.raiz = raiz
        self.raiz.title(TITULO_JANELA)
        self.raiz.geometry("640x560")
        self.raiz.minsize(540, 480)

        self.campos = {}
        self.fg_padrao = {}
        self.valores = {}
        self._mtime_carregado = self._ultima_escrita = 0.0

        topo = ctk.CTkFrame(self.raiz, corner_radius=0)
        topo.pack(fill="x")
        ctk.CTkLabel(topo, text="CENTRAL — DIAMANTE ROXO",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(side="left", padx=14, pady=10)
        ctk.CTkButton(topo, text="Recarregar", width=110, command=self._recarregar).pack(side="right", padx=12, pady=8)

        self.abts = ctk.CTkTabview(self.raiz)
        self.abts.pack(fill="both", expand=True, padx=8, pady=(6, 0))

        self._montar_trava()
        self._montar_aba_formulario("Modo")
        self._montar_aba_grupos(
            "Pausa",
            [("PAUSA POR QUANTIDADE", ["pausa_apos_filmes", "oraculo_ativado"]),
             ("HORARIOS DE RETORNO", ["pausa_retorno", "oraculo_retorno"])],
        )
        self._montar_aba_formulario("OBS")
        self._montar_aba_grupos(
            "Agendamentos",
            [("APPS", ["mixitup", "streamerbot", "kickerino", "chatty",
                        "obs64studio", "minimizar_janelas"]),
             ("SISTEMA / OBS", ["conectar_obs", "start_sistema", "retornar_midias", "iniciar_midias"])],
        )

        self.status = ctk.CTkLabel(self.raiz, text="Aguardando...", text_color=COR_NEUTRA)
        self.status.pack(side="bottom", fill="x", padx=12, pady=(4, 8))

        self._recarregar()
        self._ativar_vigilancia()

    def _montar_trava(self):
        pagina = self.abts.add("Trava")
        ctk.CTkLabel(
            pagina,
            text="Bloqueio que impede a execucao acidental do sistema.",
            text_color=COR_NEUTRA,
        ).pack(pady=(30, 6))
        self.lbl_trava = ctk.CTkLabel(pagina, text="?", font=ctk.CTkFont(size=16, weight="bold"))
        self.lbl_trava.pack(pady=10)
        self.btn_trava = ctk.CTkButton(pagina, text="...", width=280, height=52,
                                       font=ctk.CTkFont(size=15, weight="bold"),
                                       command=self._alternar_trava)
        self.btn_trava.pack(pady=14)
        ctk.CTkLabel(
            pagina,
            text="LIGAR = o sistema pode iniciar | DESLIGAR = bloqueado.\n"
                 "O proprio script reescreve 'no' ao encerrar a transmissao.",
            text_color=COR_NEUTRA,
        ).pack(pady=(24, 0))

    def _criar_campo(self, mestre, chave, tipo):
        if tipo in ("enum", "bool"):
            widget = ctk.CTkOptionMenu(mestre, values=OPCOES.get(chave, []), width=190)
            widget.configure(command=lambda v, c=chave: self._salvar_campo(c, "enum"))
        else:
            widget = ctk.CTkEntry(mestre, width=190)
            widget.bind("<FocusOut>", lambda e, c=chave, t=tipo: self._salvar_campo(c, t))
            widget.bind("<Return>", lambda e, c=chave, t=tipo: self._salvar_campo(c, t))
            widget.bind("<KeyRelease>", lambda e, c=chave, t=tipo: self._pintar(c, t))
        self.campos[chave] = (widget, tipo)
        self.fg_padrao[chave] = widget.cget("fg_color")
        return widget

    def _montar_aba_formulario(self, aba_nome):
        pagina = self.abts.add(aba_nome)
        pagina.grid_columnconfigure((1, 3), weight=1, uniform="campo")
        pagina.grid_columnconfigure((0, 2), uniform="rotulo")
        itens = [c for c in CAMPOS if c[0] == aba_nome]
        for col, (_, chave, rotulo, tipo) in enumerate(itens):
            linha, coluna = divmod(col, 2)
            ctk.CTkLabel(pagina, text=rotulo).grid(row=linha, column=coluna * 2,
                                                   sticky="w", padx=(18, 8), pady=8)
            self._criar_campo(pagina, chave, tipo).grid(row=linha, column=coluna * 2 + 1,
                                                        sticky="w", padx=(0, 18), pady=8)

    def _montar_aba_grupos(self, aba_nome, grupos):
        pagina = self.abts.add(aba_nome)
        for g, (titulo, chaves) in enumerate(grupos):
            if len(grupos) > 1:
                pagina.grid_columnconfigure(g, weight=1)
            quadro = ctk.CTkFrame(pagina)
            quadro.grid(row=0, column=g, sticky="nw", padx=(16, 4), pady=8)
            quadro.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(quadro, text=titulo, font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=COR_OK).grid(row=0, column=0, columnspan=2,
                                                 sticky="w", padx=12, pady=(10, 2))
            for r, chave in enumerate(chaves, 1):
                rotulo = next(c[2] for c in CAMPOS if c[1] == chave)
                tipo = next(c[3] for c in CAMPOS if c[1] == chave)
                ctk.CTkLabel(quadro, text=rotulo).grid(row=r, column=0, sticky="w",
                                                       padx=(12, 8), pady=6)
                self._criar_campo(quadro, chave, tipo).grid(row=r, column=1, sticky="w",
                                                             padx=(0, 12), pady=6)

    def _salvar_campo(self, chave, tipo):
        widget, _ = self.campos[chave]
        texto = widget.get()
        if tipo == "enum":
            valido = _validar_enum(chave, texto)
        else:
            valido = validar(tipo, texto)
        if not valido:
            self._pintar(chave, tipo)
            self._status(f"NAO SALVO: campo '{chave}' com valor invalido. Corrija para gravar.", COR_ERRO)
            return
        widget.configure(fg_color=self.fg_padrao[chave])
        valor = texto.strip()
        if self.valores.get(chave) == valor:
            self._status("Sem mudanca neste campo.", COR_NEUTRA)
            return
        try:
            self._ultima_escrita = gravar_chave(CAMINHO_PAINEL, chave, valor)
            self._mtime_carregado = self._ultima_escrita
        except OSError as erro:
            self._status(f"Falha ao gravar '{chave}': {erro}", COR_ERRO)
            return
        self.valores[chave] = valor
        self._status(f"Salvo: {chave} = {valor} (tempo real).", COR_OK)
        self._atualizar_controles_trava()

    def _pintar(self, chave, tipo):
        widget, _ = self.campos[chave]
        texto = widget.get()
        if tipo == "enum":
            valido = _validar_enum(chave, texto)
        else:
            valido = validar(tipo, texto)
        widget.configure(fg_color=self.fg_padrao[chave] if valido else COR_FUNDO_INVALIDA)

    def _alternar_trava(self):
        atual = self.valores.get("executar_sistema", "no").strip().lower()
        ativo = atual in ("yes", "sim", "true")
        novo = "no" if ativo else "yes"
        try:
            self._ultima_escrita = gravar_chave(CAMINHO_PAINEL, "executar_sistema", novo)
            self._mtime_carregado = self._ultima_escrita
        except OSError as erro:
            self._status(f"Falha ao gravar a trava: {erro}", COR_ERRO)
            return
        self.valores["executar_sistema"] = novo
        self._atualizar_controles_trava()
        self._status(f"Trava alterada: executar_sistema = {novo} (tempo real).", COR_OK)

    def _atualizar_controles_trava(self):
        atual = self.valores.get("executar_sistema", "no").strip().lower()
        ativo = atual in ("yes", "sim", "true")
        if ativo:
            self.lbl_trava.configure(text="SISTEMA LIBERADO", text_color="#6ab04c")
            self.btn_trava.configure(text="DESLIGAR SISTEMA", fg_color="#2f9e44", hover_color="#2b8a3e")
        else:
            self.lbl_trava.configure(text="SISTEMA BLOQUEADO", text_color="#eb4d4b")
            self.btn_trava.configure(text="LIGAR SISTEMA", fg_color="#e03131", hover_color="#c92a2a")

    def _recarregar(self):
        self.valores = ler_painel(CAMINHO_PAINEL)
        self.valores = {k: _canonizar(k, v) for k, v in self.valores.items()}
        if not self.valores:
            self._status("Aviso: Painel_de_Controle.txt nao encontrado ao lado deste arquivo. "
                         "Campos em branco; o primeiro salvamento cria o arquivo.", COR_AVISO)
        for chave, (widget, tipo) in self.campos.items():
            valor = self.valores.get(chave, "")
            if tipo in ("enum", "bool"):
                if valor and valor not in widget.cget("values"):
                    widget.configure(values=[*widget.cget("values"), valor])
                widget.set(valor)
            else:
                widget.delete(0, "end")
                widget.insert(0, valor)
                widget.configure(fg_color=self.fg_padrao[chave])
        try:
            self._mtime_carregado = self._ultima_escrita = os.path.getmtime(CAMINHO_PAINEL)
        except OSError:
            self._mtime_carregado = self._ultima_escrita = 0.0
        self._atualizar_controles_trava()
        self._status("Painel carregado. Auto-salva em tempo real a cada campo valido.", COR_OK)

    def _ativar_vigilancia(self):
        try:
            atual = os.path.getmtime(CAMINHO_PAINEL)
            if atual != self._mtime_carregado and atual != self._ultima_escrita:
                self._recarregar()
                self._status("Painel alterado de fora da janela. Campos recarregados.", COR_AVISO)
        except OSError:
            pass
        self.raiz.after(1500, self._ativar_vigilancia)

    def _status(self, texto, cor):
        self.status.configure(text=texto, text_color=cor)


def _instancia_unica_disponivel():
    global _handle_mutex
    try:
        kernel32 = ctypes.windll.kernel32
        _handle_mutex = kernel32.CreateMutexW(None, False, NOME_MUTEX)
        return kernel32.GetLastError() != 183
    except Exception:
        return True


def _focar_janela_existente():
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, TITULO_JANELA)
    except Exception:
        hwnd = None
    if hwnd:
        try:
            user32.SetForegroundWindow(hwnd)
            user32.ShowWindow(hwnd, 9)
        except Exception:
            pass
        return
    try:
        ctypes.windll.user32.MessageBoxW(
            0,
            "A Central já está aberta.\nEntre na janela já existente.",
            TITULO_JANELA,
            0x40,
        )
    except Exception:
        pass


def main():
    if not _instancia_unica_disponivel():
        _focar_janela_existente()
        return
    raiz = ctk.CTk()
    CentralApp(raiz)
    raiz.mainloop()


if __name__ == "__main__":
    main()
