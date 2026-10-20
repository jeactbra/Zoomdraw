#!/usr/bin/env python3
# ZoomDraw - camada de desenho sobre a tela (estilo ZoomIt) para Linux Mint
# Funciona em segundo plano:
#   zoomdraw            -> inicia em segundo plano (sem mostrar nada)
#   zoomdraw desenhar   -> mostra/oculta a camada de desenho (usado pelo Ctrl+Shift+1)
#   zoomdraw exit       -> encerra o aplicativo de vez
#   ESC apenas oculta a camada; o app continua esperando o atalho.
#
# Teclas:
#   r g b y p k  -> cor (vermelho, verde, azul, amarelo, rosa, preto)
#   + / -        -> espessura do traço
#   Ctrl+Z       -> desfazer
#   e            -> apagar tudo
#   h            -> mostrar/ocultar a barra de opções
#   ESC          -> ocultar a camada (o app continua em segundo plano)
# Atalho global: Ctrl+Shift+1 (tecla 1 ! ¹), capturado pelo próprio app via Keybinder
# Mouse: botão esquerdo desenha; segure SHIFT para linha reta.
# A barra no rodapé também é clicável (cores, espessura, desfazer, limpar, sair).

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, Gio, GLib
try:
    gi.require_version("GdkX11", "3.0")
    from gi.repository import GdkX11
except (ValueError, ImportError):
    GdkX11 = None
try:
    gi.require_version("Keybinder", "3.0")
    from gi.repository import Keybinder
except (ValueError, ImportError):
    Keybinder = None
import cairo
import subprocess
import sys
import ast
import os

CORES = {
    "r": (1, 0, 0), "g": (0, 0.8, 0), "b": (0, 0.4, 1),
    "y": (1, 0.85, 0), "p": (1, 0, 1), "k": (0, 0, 0),
}

DICA = "Shift = reta   |   r g b y p k = cor   |   + / - = espessura   |   Ctrl+Z = desfazer   |   e = limpar   |   h = ocultar barra   |   Esc = ocultar   |   zoomdraw exit = encerrar"


class Overlay(Gtk.Window):
    def __init__(self, app):
        super().__init__(type=Gtk.WindowType.TOPLEVEL, application=app)
        self.app = app
        tela = self.get_screen()
        visual = tela.get_rgba_visual()
        if visual is not None and tela.is_composited():
            self.set_visual(visual)
        else:
            print("Aviso: compositor não ativo; o fundo pode não ficar transparente.")

        self.set_app_paintable(True)
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.fullscreen()

        self.tracos = []      # lista de (cor, largura, [pontos])
        self.atual = None
        self.cor = CORES["r"]
        self.largura = 4
        self.reta = False
        self.mostrar_barra = True
        self.botoes = []      # lista de (x, y, w, h, acao) para cliques na barra

        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK
                        | Gdk.EventMask.BUTTON_RELEASE_MASK
                        | Gdk.EventMask.POINTER_MOTION_MASK)
        self.connect("draw", self.on_draw)
        self.connect("button-press-event", self.on_press)
        self.connect("button-release-event", self.on_release)
        self.connect("motion-notify-event", self.on_motion)
        self.connect("key-press-event", self.on_key)
        self.connect("delete-event", lambda *a: self.ocultar() or True)

    # ---------- desenho ----------
    def on_draw(self, w, cr):
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        for cor, larg, pts in self.tracos + ([self.atual] if self.atual else []):
            if len(pts) < 2:
                continue
            cr.set_source_rgb(*cor)
            cr.set_line_width(larg)
            cr.move_to(*pts[0])
            for p in pts[1:]:
                cr.line_to(*p)
            cr.stroke()
        self.botoes = []
        if self.mostrar_barra:
            self.desenhar_barra(cr, w.get_allocated_width(), w.get_allocated_height())

    def botao_texto(self, cr, x, y, h, texto, acao):
        cr.set_font_size(15)
        larg = cr.text_extents(texto).x_advance + 20
        cr.set_source_rgba(1, 1, 1, 0.15)
        cr.rectangle(x, y, larg, h)
        cr.fill()
        cr.set_source_rgb(1, 1, 1)
        cr.move_to(x + 10, y + h / 2 + 5)
        cr.show_text(texto)
        self.botoes.append((x, y, larg, h, acao))
        return x + larg + 8

    def desenhar_barra(self, cr, W, H):
        alt_barra = 74
        y0 = H - alt_barra
        cr.set_source_rgba(0.1, 0.1, 0.1, 0.85)
        cr.rectangle(0, y0, W, alt_barra)
        cr.fill()
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)

        # linha 1: botões
        x, y, h = 12, y0 + 8, 30
        for tecla, cor in CORES.items():
            cr.set_source_rgb(*cor)
            cr.rectangle(x, y, h, h)
            cr.fill()
            if cor == self.cor:
                cr.set_source_rgb(1, 1, 1)
                cr.set_line_width(3)
                cr.rectangle(x - 2, y - 2, h + 4, h + 4)
                cr.stroke()
            self.botoes.append((x, y, h, h, ("cor", tecla)))
            x += h + 8
        x += 10
        x = self.botao_texto(cr, x, y, h, "−", ("menos", None))
        # amostra da espessura atual
        cr.set_source_rgb(*self.cor)
        cr.arc(x + 20, y + h / 2, max(self.largura / 2, 1), 0, 6.2832)
        cr.fill()
        cr.set_source_rgb(1, 1, 1)
        cr.set_font_size(13)
        cr.move_to(x + 44, y + h / 2 + 5)
        cr.show_text(f"{self.largura}px")
        x += 90
        x = self.botao_texto(cr, x, y, h, "+", ("mais", None))
        x += 10
        x = self.botao_texto(cr, x, y, h, "Desfazer", ("desfazer", None))
        x = self.botao_texto(cr, x, y, h, "Limpar", ("limpar", None))
        x = self.botao_texto(cr, x, y, h, "Ocultar (Esc)", ("ocultar", None))
        x = self.botao_texto(cr, x, y, h, "Encerrar app", ("sair", None))

        # linha 2: atalhos
        cr.set_source_rgba(1, 1, 1, 0.8)
        cr.set_font_size(13)
        cr.move_to(12, y0 + alt_barra - 10)
        cr.show_text(DICA)

    # ---------- visibilidade ----------
    def mostrar(self, ts=0):
        self.fullscreen()
        self.show_all()
        # sem um timestamp válido o Cinnamon bloqueia a troca de foco
        # (a camada aparece, mas o teclado continua na janela anterior)
        gw = self.get_window()
        if not ts and GdkX11 is not None and isinstance(gw, GdkX11.X11Window):
            ts = GdkX11.x11_get_server_time(gw)
        self.present_with_time(ts or Gdk.CURRENT_TIME)

    def ocultar(self):
        self.atual = None
        self.tracos.clear()   # como no ZoomIt: ao sair, o desenho é apagado
        self.hide()

    def alternar(self, ts=0):
        if self.get_visible():
            self.ocultar()
        else:
            self.mostrar(ts)

    # ---------- ações ----------
    def executar(self, acao, arg=None):
        if acao == "sair":
            self.app.quit()
            return
        elif acao == "ocultar":
            self.ocultar()
            return
        elif acao == "desfazer":
            if self.tracos:
                self.tracos.pop()
        elif acao == "limpar":
            self.tracos.clear()
        elif acao == "mais":
            self.largura = min(self.largura + 2, 40)
        elif acao == "menos":
            self.largura = max(self.largura - 2, 1)
        elif acao == "cor":
            self.cor = CORES[arg]
        elif acao == "barra":
            self.mostrar_barra = not self.mostrar_barra
        self.queue_draw()

    # ---------- mouse ----------
    def on_press(self, _w, ev):
        if ev.button != 1:
            return
        for bx, by, bw, bh, (acao, arg) in self.botoes:
            if bx <= ev.x <= bx + bw and by <= ev.y <= by + bh:
                self.executar(acao, arg)
                return
        self.reta = bool(ev.state & Gdk.ModifierType.SHIFT_MASK)
        self.atual = (self.cor, self.largura, [(ev.x, ev.y)])

    def on_motion(self, _w, ev):
        if self.atual:
            pts = self.atual[2]
            if self.reta:
                del pts[1:]
            pts.append((ev.x, ev.y))
            self.queue_draw()

    def on_release(self, _w, ev):
        if ev.button == 1 and self.atual:
            self.tracos.append(self.atual)
            self.atual = None
            self.queue_draw()

    # ---------- teclado ----------
    def on_key(self, _w, ev):
        nome = Gdk.keyval_name(ev.keyval) or ""
        ctrl = ev.state & Gdk.ModifierType.CONTROL_MASK
        if nome == "Escape":
            self.executar("ocultar")
        elif ctrl and nome.lower() == "z":
            self.executar("desfazer")
        elif nome == "e":
            self.executar("limpar")
        elif nome == "h":
            self.executar("barra")
        elif nome in ("plus", "equal", "KP_Add"):
            self.executar("mais")
        elif nome in ("minus", "KP_Subtract"):
            self.executar("menos")
        elif nome in CORES:
            self.executar("cor", nome)


APP_ID = "br.jean.zoomdraw"
# O Keybinder considera o Shift "consumido" ao gerar o "!", então Ctrl+Shift+1
# precisa ser registrado como <Ctrl>exclam; "<Ctrl><Shift>exclam" é capturado
# mas nunca dispara o callback.
ATALHOS = ["<Ctrl>exclam", "<Ctrl><Shift>1"]  # usa o primeiro que funcionar
MSG_ATALHO = "Ctrl+Shift+1 mostra/oculta o desenho; 'zoomdraw exit' encerra."

SCHEMA = "org.cinnamon.desktop.keybindings"


def remover_atalho_antigo():
    """Remove o atalho do Cinnamon criado pela versão 1.1/1.2 (evita conflito)."""
    try:
        r = subprocess.run(["gsettings", "get", SCHEMA, "custom-list"],
                           capture_output=True, text=True)
        lista = ast.literal_eval(r.stdout.strip().replace("@as ", "") or "[]")
        if "zoomdraw" in lista:
            lista.remove("zoomdraw")
            subprocess.run(["gsettings", "set", SCHEMA, "custom-list", str(lista)])
    except Exception:
        pass


def ja_esta_aberto():
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        r = bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus",
                          "org.freedesktop.DBus", "NameHasOwner",
                          GLib.Variant("(s)", (APP_ID,)), GLib.VariantType("(b)"),
                          Gio.DBusCallFlags.NONE, -1, None)
        return r.unpack()[0]
    except Exception:
        return False


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.janela = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        self.hold()   # mantém o app vivo mesmo sem janela visível
        self.janela = Overlay(self)
        if Keybinder is None:
            print("AVISO: biblioteca Keybinder ausente; instale gir1.2-keybinder-3.0. "
                  "Use 'zoomdraw desenhar' enquanto isso.", flush=True)
            return
        Keybinder.init()
        ok = False
        for a in ATALHOS:          # registra só UMA forma, para não disparar em dobro
            try:
                if Keybinder.bind(a, self.on_atalho):
                    ok = True
                    print(f"Atalho registrado: {a}", flush=True)
                    break
            except Exception:
                pass
        if not ok:
            print("AVISO: não foi possível registrar Ctrl+Shift+1 "
                  "(outra aplicação pode estar usando essa tecla).", flush=True)

    def on_atalho(self, *_):
        # proteção extra: ignora disparos repetidos em menos de 0,4 s
        agora = GLib.get_monotonic_time()
        if agora - getattr(self, "_ultimo", 0) < 400000:
            return
        self._ultimo = agora
        ts = Keybinder.get_current_event_time()
        GLib.idle_add(self._alternar_uma_vez, ts)

    def _alternar_uma_vez(self, ts):
        self.janela.alternar(ts)
        return False

    def do_command_line(self, cmdline):
        args = cmdline.get_arguments()[1:]
        if "exit" in args or "sair" in args:
            self.quit()
        elif "desenhar" in args or "draw" in args:
            self.janela.alternar()
        return 0


def main():
    args = sys.argv[1:]

    # processo de fundo (iniciado por nós mesmos)
    if os.environ.get("ZOOMDRAW_FUNDO") == "1":
        remover_atalho_antigo()
        sys.exit(App().run(sys.argv))

    aberto = ja_esta_aberto()

    if "exit" in args or "sair" in args:
        if aberto:
            App().run(sys.argv)          # repassa o pedido ao app aberto
            print("ZoomDraw encerrado.")
        else:
            print("ZoomDraw não estava aberto.")
        return

    if aberto:
        if "desenhar" in args or "draw" in args:
            App().run(sys.argv)
        else:
            print("ZoomDraw já está aberto em segundo plano.")
            print(MSG_ATALHO)
        return

    # não está aberto: inicia em segundo plano, separado do terminal
    env = dict(os.environ, ZOOMDRAW_FUNDO="1")
    log = open(os.path.join(GLib.get_user_cache_dir(), "zoomdraw.log"), "a")
    subprocess.Popen([sys.executable, os.path.abspath(__file__), *args],
                     env=env, stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                     start_new_session=True)
    print("ZoomDraw aberto em segundo plano.")
    print(MSG_ATALHO)
    if Keybinder is None:
        print("AVISO: instale 'gir1.2-keybinder-3.0' para o atalho funcionar.")


if __name__ == "__main__":
    main()
