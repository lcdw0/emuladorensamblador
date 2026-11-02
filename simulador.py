"""simulador gráfico de ensamblador en Python + Tkinter.

Ejecutar: py simulador.py
"""
from __future__ import annotations

from pathlib import Path
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

from motor import CPU, ErrorEnsamblador, ARIDAD, REGISTROS


# Paleta propia: los colores se concentran aquí para facilitar su modificación.
COLORES = {
    "fondo": "#0A1020",
    "panel": "#131D30",
    "panel_alt": "#18263C",
    "editor": "#0E1729",
    "borde": "#2A3A53",
    "texto": "#EDF4FF",
    "suave": "#9FB1CB",
    "verde": "#55E3C1",
    "verde_oscuro": "#153E3D",
    "azul": "#78B5FF",
    "amarillo": "#F2C778",
    "rojo": "#FF8591",
    "actual": "#263B4A",
    "anterior": "#1B3340",
    "error": "#4D2733",
}
CARPETA = Path(__file__).resolve().parent
EJEMPLOS = {
    "01 · Suma": "01_suma.asm",
    "02 · Contador": "02_contador.asm",
    "03 · Condiciones": "03_condiciones.asm",
    "04 · Fibonacci": "04_fibonacci.asm",
}


class Aplicacion(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ASM Lab | Simulador de ensamblador")
        self.geometry("1250x790")
        self.minsize(1030, 680)
        self.configure(bg=COLORES["fondo"])

        self.cpu: CPU | None = None
        self.ejecutando = False
        self.temporizador: str | None = None
        self.pausado_en_breakpoint = False
        self.ignorar_breakpoint_una_vez = False
        self.puntos: set[int] = set()
        self.archivo_actual: Path | None = None
        self.pasos_sesion = 0
        self.tarea_colorear: str | None = None
        self.fuente_codigo = tkfont.Font(family="Consolas", size=12)
        self.fuente_numero = tkfont.Font(family="Consolas", size=19, weight="bold")
        self._configurar_estilo()
        self._crear_vista()
        self._atajos()
        self._cargar_ejemplo("02 · Contador", preguntar=False)
        self.protocol("WM_DELETE_WINDOW", self._cerrar)

    def _configurar_estilo(self):
        estilo = ttk.Style(self)
        try:
            estilo.theme_use("clam")
        except tk.TclError:
            pass
        estilo.configure("ASM.TCombobox", fieldbackground=COLORES["panel_alt"],
                         background=COLORES["panel_alt"], foreground=COLORES["texto"],
                         bordercolor=COLORES["borde"], arrowcolor=COLORES["texto"], padding=7)
        estilo.map("ASM.TCombobox", fieldbackground=[("readonly", COLORES["panel_alt"])],
                   foreground=[("readonly", COLORES["texto"])])

    def _etiqueta(self, padre, texto, *, tam=10, color="texto", negrita=False, **kwargs):
        return tk.Label(padre, text=texto, fg=COLORES.get(color, color),
                        bg=padre.cget("bg"), anchor="w",
                        font=("Segoe UI", tam, "bold" if negrita else "normal"), **kwargs)

    def _boton(self, padre, texto, accion, color="panel_alt", fg="texto", **kwargs):
        boton = tk.Button(padre, text=texto, command=accion, relief="flat",
                          bg=COLORES[color], fg=COLORES[fg],
                          activebackground=COLORES["borde"], activeforeground=COLORES["texto"],
                          borderwidth=0, cursor="hand2", padx=13, pady=9,
                          font=("Segoe UI", 10, "bold"), **kwargs)
        return boton

    def _panel(self, padre, **kwargs):
        return tk.Frame(padre, bg=COLORES["panel"], highlightthickness=1,
                        highlightbackground=COLORES["borde"], **kwargs)

    def _crear_vista(self):
        encabezado = tk.Frame(self, bg=COLORES["fondo"])
        encabezado.pack(fill="x", padx=22, pady=(19, 12))
        tk.Label(encabezado, text="ASM", bg=COLORES["verde"], fg=COLORES["fondo"],
                 font=("Segoe UI", 13, "bold"), padx=12, pady=5).pack(side="left")
        self._etiqueta(encabezado, "  LAB", tam=19, negrita=True).pack(side="left")
        self._etiqueta(encabezado, "   /   Laboratorio de lenguaje ensamblador", tam=10,
                       color="suave").pack(side="left", pady=9)
        self._etiqueta(encabezado, "PYTHON  +  TKINTER", tam=9,
                       color="verde", negrita=True).pack(side="right", pady=9)

        barra = tk.Frame(self, bg=COLORES["panel"], padx=13, pady=10)
        barra.pack(fill="x", padx=22, pady=(0, 12))
        self.botones: dict[str, tk.Button] = {}
        controles = [
            ("ejecutar", "▶  Ejecutar  F5", self.ejecutar, "verde", "fondo"),
            ("paso", "⇥  Paso  F7", self.paso, "panel_alt", "texto"),
            ("retroceder", "↶  Atrás", self.retroceder, "panel_alt", "texto"),
            ("pausar", "Ⅱ  Pausar", self.pausar, "panel_alt", "texto"),
            ("reiniciar", "↻  Reiniciar", self.reiniciar, "panel_alt", "texto"),
        ]
        for clave, texto, accion, bg, fg in controles:
            boton = self._boton(barra, texto, accion, bg, fg)
            boton.pack(side="left", padx=(0, 7))
            self.botones[clave] = boton
        self._boton(barra, "Abrir", self.abrir).pack(side="right", padx=(6, 0))
        self._boton(barra, "Guardar", self.guardar).pack(side="right", padx=(6, 0))
        self._boton(barra, "?  Ayuda", self.ayuda).pack(side="right", padx=(6, 0))

        principal = tk.PanedWindow(self, orient="horizontal", bg=COLORES["fondo"],
                                   bd=0, sashwidth=11, sashrelief="flat", showhandle=False)
        principal.pack(fill="both", expand=True, padx=22, pady=(0, 10))
        izquierdo = self._panel(principal)
        derecho = tk.Frame(principal, bg=COLORES["fondo"])
        principal.add(izquierdo, minsize=460, stretch="always", width=680)
        principal.add(derecho, minsize=360, stretch="always", width=470)
        self._crear_editor(izquierdo)
        self._crear_lateral(derecho)

        inferior = tk.Frame(self, bg=COLORES["fondo"])
        inferior.pack(side="bottom", fill="x", padx=23, pady=(0, 12), before=principal)
        self.estado = tk.StringVar(value="Listo para escribir instrucciones.")
        self.etiqueta_estado = self._etiqueta(inferior, "", color="suave", tam=10)
        self.etiqueta_estado.configure(textvariable=self.estado)
        self.etiqueta_estado.pack(side="left")
        self._etiqueta(inferior, "F5 ejecutar  ·  F7 paso  ·  F8 pausar  ·  Ctrl+S guardar",
                       color="suave", tam=9).pack(side="right")
        self._actualizar_controles()

    def _crear_editor(self, padre):
        cabecera = tk.Frame(padre, bg=COLORES["panel"], padx=15, pady=13)
        cabecera.pack(fill="x")
        self._etiqueta(cabecera, "EDITOR DE CÓDIGO", color="texto", negrita=True,
                       tam=11).pack(side="left")
        self.var_ejemplo = tk.StringVar()
        selector = ttk.Combobox(cabecera, textvariable=self.var_ejemplo,
                                values=list(EJEMPLOS), width=21, state="readonly",
                                style="ASM.TCombobox", font=("Segoe UI", 9))
        selector.pack(side="right")
        selector.bind("<<ComboboxSelected>>", self._seleccionar_ejemplo)
        cuerpo = tk.Frame(padre, bg=COLORES["editor"])
        cuerpo.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        cuerpo.grid_columnconfigure(1, weight=1)
        cuerpo.grid_rowconfigure(0, weight=1)
        self.gutter = tk.Text(cuerpo, width=5, bd=0, relief="flat",
                              bg=COLORES["panel_alt"], fg=COLORES["suave"],
                              font=self.fuente_codigo, padx=7, pady=12,
                              wrap="none", state="disabled", cursor="hand2", takefocus=0)
        self.gutter.grid(row=0, column=0, sticky="ns")
        self.gutter.tag_configure("break", foreground=COLORES["rojo"])
        self.gutter.bind("<Button-1>", self._alternar_punto)
        self.editor = tk.Text(cuerpo, undo=True, wrap="none", bd=0, relief="flat",
                              bg=COLORES["editor"], fg=COLORES["texto"],
                              insertbackground=COLORES["verde"], selectbackground="#365876",
                              font=self.fuente_codigo, padx=14, pady=12,
                              highlightthickness=0, tabs=(28,))
        self.editor.grid(row=0, column=1, sticky="nsew")
        self.scroll_y = tk.Scrollbar(cuerpo, command=self._desplazar_editor,
                                   bg=COLORES["panel_alt"], troughcolor=COLORES["panel"],
                                   activebackground=COLORES["borde"], width=12)
        self.scroll_y.grid(row=0, column=2, sticky="ns")
        self.editor.config(yscrollcommand=self._sincronizar_scroll)
        self.scroll_x = tk.Scrollbar(cuerpo, orient="horizontal", command=self.editor.xview,
                                   bg=COLORES["panel_alt"], troughcolor=COLORES["panel"], width=11)
        self.scroll_x.grid(row=1, column=1, sticky="ew")
        self.editor.config(xscrollcommand=self.scroll_x.set)
        self.editor.tag_configure("comentario", foreground="#7185A3")
        self.editor.tag_configure("operacion", foreground=COLORES["azul"])
        self.editor.tag_configure("registro", foreground=COLORES["verde"])
        self.editor.tag_configure("etiqueta", foreground=COLORES["amarillo"])
        self.editor.tag_configure("inmediato", foreground="#D7B9FF")
        self.editor.tag_configure("anterior", background=COLORES["anterior"])
        self.editor.tag_configure("actual", background=COLORES["actual"])
        self.editor.tag_configure("error", background=COLORES["error"])
        self.editor.bind("<<Modified>>", self._editor_modificado)
        pie = tk.Frame(padre, bg=COLORES["panel"], padx=15, pady=5)
        pie.pack(side="bottom", fill="x", before=cuerpo)
        self._etiqueta(pie, "● Clic en el número de línea = punto de interrupción",
                       color="suave", tam=9).pack(side="left")
        self._etiqueta(pie, "; = comentario", color="suave", tam=9).pack(side="right")

    def _crear_lateral(self, padre):
        registros = self._panel(padre)
        registros.pack(fill="x", pady=(0, 11))
        self._etiqueta(registros, "  REGISTROS DE LA CPU", negrita=True,
                       tam=11).pack(anchor="w", padx=8, pady=(12, 8))
        cuadrilla = tk.Frame(registros, bg=COLORES["panel"])
        cuadrilla.pack(fill="x", padx=12, pady=(0, 12))
        for col in range(2):
            cuadrilla.grid_columnconfigure(col, weight=1, uniform="cols")
        self.cartas = {}
        for i, reg in enumerate(REGISTROS):
            caja = tk.Frame(cuadrilla, bg=COLORES["panel_alt"], padx=13, pady=9)
            caja.grid(row=i // 2, column=i % 2, padx=4, pady=4, sticky="ew")
            self._etiqueta(caja, reg, color="suave", negrita=True, tam=10).pack(anchor="w")
            valor = tk.Label(caja, text="0", font=self.fuente_numero,
                             bg=COLORES["panel_alt"], fg=COLORES["texto"], anchor="w")
            valor.pack(anchor="w")
            extra = self._etiqueta(caja, "HEX 0x0000  ·  BIN 0000 0000", color="suave", tam=8)
            extra.pack(anchor="w", pady=(3, 0))
            self.cartas[reg] = (valor, extra)

        indicadores = self._panel(padre)
        indicadores.pack(fill="x", pady=(0, 11))
        inf = tk.Frame(indicadores, bg=COLORES["panel"], padx=14, pady=9)
        inf.pack(fill="x")
        self._etiqueta(inf, "PC", color="suave", tam=10, negrita=True).pack(side="left")
        self.pc_label = self._etiqueta(inf, "00", color="azul", tam=16, negrita=True)
        self.pc_label.pack(side="left", padx=(10, 24))
        self._etiqueta(inf, "Z", color="suave", tam=10, negrita=True).pack(side="left")
        self.z_label = self._etiqueta(inf, "0", color="suave", tam=16, negrita=True)
        self.z_label.pack(side="left", padx=(9, 20))
        self._etiqueta(inf, "N", color="suave", tam=10, negrita=True).pack(side="left")
        self.n_label = self._etiqueta(inf, "0", color="suave", tam=16, negrita=True)
        self.n_label.pack(side="left", padx=(9, 0))
        self.instruccion_var = tk.StringVar(value="Siguiente: sin compilar")
        self._etiqueta(indicadores, "", color="suave", tam=10,
                       textvariable=self.instruccion_var).pack(fill="x", padx=14, pady=(0, 10))

        inferior = self._panel(padre)
        inferior.pack(fill="both", expand=True)
        cab = tk.Frame(inferior, bg=COLORES["panel"], padx=14, pady=9)
        cab.pack(fill="x")
        self._etiqueta(cab, "CONSOLA DE SALIDA", negrita=True, tam=10).pack(side="left")
        self._etiqueta(cab, "PRINT", color="verde", tam=9).pack(side="right")
        self.consola = tk.Text(inferior, height=3, state="disabled", bd=0,
                               bg=COLORES["editor"], fg=COLORES["verde"],
                               font=("Consolas", 11), padx=12, pady=8,
                               wrap="word", highlightthickness=0)
        self.consola.pack(fill="both", expand=True, padx=10)
        control_velocidad = tk.Frame(inferior, bg=COLORES["panel"], padx=11, pady=5)
        control_velocidad.pack(fill="x")
        self._etiqueta(control_velocidad, "Velocidad", color="suave", tam=9).pack(side="left")
        self.velocidad = tk.IntVar(value=300)
        escala = tk.Scale(control_velocidad, from_=1000, to=50, resolution=50,
                          orient="horizontal", variable=self.velocidad,
                          showvalue=False, borderwidth=0, highlightthickness=0,
                          bg=COLORES["panel"], fg=COLORES["texto"],
                          activebackground=COLORES["verde"], troughcolor=COLORES["panel_alt"],
                          length=170, sliderlength=14)
        escala.pack(side="left", fill="x", expand=True, padx=8)
        self.velocidad_label = self._etiqueta(control_velocidad, "300 ms", color="suave", tam=9)
        self.velocidad_label.pack(side="right")
        self.velocidad.trace_add("write", lambda *_: self.velocidad_label.configure(text=f"{self.velocidad.get()} ms"))
        pie = tk.Frame(inferior, bg=COLORES["panel"], padx=14, pady=4)
        pie.pack(fill="x")
        self._etiqueta(pie, "HISTORIAL DE EJECUCIÓN", negrita=True, tam=10).pack(side="left")
        self.conteo_label = self._etiqueta(pie, "0 pasos", color="suave", tam=9)
        self.conteo_label.pack(side="right")
        self.traza = tk.Text(inferior, height=3, state="disabled", bd=0,
                             bg=COLORES["editor"], fg=COLORES["suave"],
                             font=("Consolas", 9), padx=12, pady=7,
                             wrap="none", highlightthickness=0)
        self.traza.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def _atajos(self):
        self.bind("<F5>", lambda e: self._atajo(self.ejecutar))
        self.bind("<F7>", lambda e: self._atajo(self.paso))
        self.bind("<F8>", lambda e: self._atajo(self.pausar))
        self.bind("<Control-r>", lambda e: self._atajo(self.reiniciar))
        self.bind("<Control-o>", lambda e: self._atajo(self.abrir))
        self.bind("<Control-s>", lambda e: self._atajo(self.guardar))
        self.bind("<Alt-Left>", lambda e: self._atajo(self.retroceder))
        self.bind("<F1>", lambda e: self._atajo(self.ayuda))

    @staticmethod
    def _atajo(accion):
        accion()
        return "break"

    def _editor_modificado(self, _evento=None):
        if self.editor.edit_modified():
            self.editor.edit_modified(False)
            if self.tarea_colorear is not None:
                self.after_cancel(self.tarea_colorear)
            self.tarea_colorear = self.after(90, self._colorear)
            self._actualizar_gutter()

    def _colorear(self):
        self.tarea_colorear = None
        for nombre in ("comentario", "operacion", "registro", "etiqueta", "inmediato"):
            self.editor.tag_remove(nombre, "1.0", "end")
        for i, linea in enumerate(self.editor.get("1.0", "end-1c").splitlines(), 1):
            prefijo = f"{i}."
            if ";" in linea:
                pos = linea.index(";")
                self.editor.tag_add("comentario", f"{prefijo}{pos}", f"{prefijo}{len(linea)}")
                linea = linea[:pos]
            for coincide in re.finditer(r"\b[A-Za-z_]\w*(?=\s*:)", linea):
                self.editor.tag_add("etiqueta", f"{prefijo}{coincide.start()}", f"{prefijo}{coincide.end()}")
            for coincide in re.finditer(r"\b[A-Za-z_][A-Za-z_0-9]*\b", linea):
                palabra = coincide.group().upper()
                if palabra in ARIDAD:
                    clase = "operacion"
                elif palabra in REGISTROS:
                    clase = "registro"
                else:
                    continue
                self.editor.tag_add(clase, f"{prefijo}{coincide.start()}", f"{prefijo}{coincide.end()}")
            for coincide in re.finditer(r"(?<!\w)(?:0[xX][0-9a-fA-F]+|0[bB][01]+|\d+)(?!\w)", linea):
                self.editor.tag_add("inmediato", f"{prefijo}{coincide.start()}", f"{prefijo}{coincide.end()}")
        self.editor.tag_raise("anterior")
        self.editor.tag_raise("actual")
        self.editor.tag_raise("error")

    def _sincronizar_scroll(self, primero, ultimo):
        self.scroll_y.set(primero, ultimo)
        self.gutter.yview_moveto(primero)

    def _desplazar_editor(self, *argumentos):
        self.editor.yview(*argumentos)
        self.gutter.yview(*argumentos)

    def _actualizar_gutter(self):
        total = int(self.editor.index("end-1c").split(".")[0])
        primera = self.editor.yview()[0]
        self.gutter.configure(state="normal")
        self.gutter.delete("1.0", "end")
        self.gutter.insert("1.0", "\n".join("●" if n in self.puntos else str(n)
                                                 for n in range(1, total + 1)))
        for n in self.puntos:
            if n <= total:
                self.gutter.tag_add("break", f"{n}.0", f"{n}.end")
        self.gutter.configure(state="disabled")
        self.gutter.yview_moveto(primera)

    def _alternar_punto(self, evento):
        linea = int(self.gutter.index(f"@0,{evento.y}").split(".")[0])
        total = int(self.editor.index("end-1c").split(".")[0])
        if not 1 <= linea <= total:
            return "break"
        if linea in self.puntos:
            self.puntos.remove(linea)
            self._estado(f"Punto de interrupción eliminado en línea {linea}.")
        else:
            self.puntos.add(linea)
            self._estado(f"Punto de interrupción agregado en línea {linea}.")
        self._actualizar_gutter()
        return "break"

    def _reemplazar_codigo(self, codigo: str):
        self.reiniciar()
        self.puntos.clear()
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", codigo.rstrip("\n") + "\n")
        self.editor.edit_modified(False)
        self._actualizar_gutter()
        self._colorear()
        self.editor.focus_set()

    def _seleccionar_ejemplo(self, _evento=None):
        elegido = self.var_ejemplo.get()
        if elegido not in EJEMPLOS:
            return
        if self.editor.get("1.0", "end-1c").strip() and not messagebox.askyesno(
            "Cambiar ejemplo", "¿Querés reemplazar el código del editor?"
        ):
            return
        self._cargar_ejemplo(elegido, preguntar=False)

    def _cargar_ejemplo(self, nombre: str, preguntar=False):
        ruta = CARPETA / "ejemplos" / EJEMPLOS[nombre]
        try:
            codigo = ruta.read_text(encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("Ejemplo no disponible", str(exc))
            return
        self._reemplazar_codigo(codigo)
        self.archivo_actual = None
        self.var_ejemplo.set(nombre)
        self._estado(f"Ejemplo cargado: {nombre}. Presioná F7 para avanzar.")

    def _preparar(self) -> bool:
        if self.cpu is not None:
            return True
        try:
            self.cpu = CPU(self.editor.get("1.0", "end-1c"))
        except ErrorEnsamblador as error:
            self._marcar_error(error.linea)
            self._estado(str(error), error=True)
            return False
        self.editor.configure(state="disabled")
        self._dibujar_cpu()
        if self.cpu.detenida:
            self._estado("No hay instrucciones que ejecutar.")
            return False
        self._estado(f"Código compilado: {len(self.cpu.programa)} instrucciones.")
        return True

    def _marcar_error(self, linea: int):
        self.editor.tag_remove("error", "1.0", "end")
        self.editor.tag_add("error", f"{linea}.0", f"{linea}.end+1c")
        self.editor.see(f"{linea}.0")

    def _resaltar(self):
        for tag in ("actual", "anterior", "error"):
            self.editor.tag_remove(tag, "1.0", "end")
        if self.cpu is None:
            return
        if self.cpu.ultima_linea is not None:
            n = self.cpu.ultima_linea
            self.editor.tag_add("anterior", f"{n}.0", f"{n}.end+1c")
        if not self.cpu.detenida:
            n = self.cpu.programa[self.cpu.pc].linea
            self.editor.tag_add("actual", f"{n}.0", f"{n}.end+1c")
            self.editor.see(f"{n}.0")

    @staticmethod
    def _texto_solo_lectura(widget, texto):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", texto)
        widget.see("end")
        widget.configure(state="disabled")

    def _dibujar_cpu(self, anteriores=None):
        registros = self.cpu.registros if self.cpu else dict.fromkeys(REGISTROS, 0)
        for nombre, valor in registros.items():
            texto, extra = self.cartas[nombre]
            texto.configure(text=str(valor), fg=(COLORES["verde"] if anteriores is not None
                                                   and anteriores[nombre] != valor else COLORES["texto"]))
            extra.configure(text=f"HEX 0x{valor & 0xFFFF:04X}  ·  BIN {valor & 0xFF:08b}")
        self.pc_label.configure(text=f"{self.cpu.pc:02d}" if self.cpu else "00")
        self.z_label.configure(text="1" if self.cpu and self.cpu.z else "0",
                               fg=COLORES["verde"] if self.cpu and self.cpu.z else COLORES["suave"])
        self.n_label.configure(text="1" if self.cpu and self.cpu.n else "0",
                               fg=COLORES["amarillo"] if self.cpu and self.cpu.n else COLORES["suave"])
        if self.cpu is None:
            siguiente = "Siguiente: sin compilar"
        elif self.cpu.detenida:
            siguiente = "Estado: programa finalizado"
        else:
            ins = self.cpu.programa[self.cpu.pc]
            siguiente = f"Siguiente: {ins.operacion} {', '.join(ins.argumentos)}".rstrip()
        self.instruccion_var.set(siguiente)
        salidas = self.cpu.salidas if self.cpu else []
        salida_visible = salidas[-300:]
        prefijo = "(Mostrando las últimas 300 salidas)\n" if len(salidas) > 300 else ""
        self._texto_solo_lectura(self.consola, prefijo + "\n".join(map(str, salida_visible)))
        eventos = list(self.cpu.eventos) if self.cpu else []
        lineas = [f"PC {evt.pc_anterior:02d}  L{evt.linea:02d}  {evt.operacion} {', '.join(evt.argumentos)}"
                  for evt in eventos]
        self._texto_solo_lectura(self.traza, "\n".join(lineas))
        self.conteo_label.configure(text=f"{self.cpu.pasos if self.cpu else 0} pasos")
        self._resaltar()
        self._actualizar_controles()

    def _estado(self, texto: str, error=False):
        self.estado.set(texto)
        self.etiqueta_estado.configure(fg=COLORES["rojo"] if error else COLORES["suave"])

    def _actualizar_controles(self):
        vivo = self.cpu is not None and not self.cpu.detenida
        retrocedible = self.cpu is not None and bool(self.cpu.historial)
        self.botones["ejecutar"].configure(state="normal" if not self.ejecutando and (self.cpu is None or vivo) else "disabled")
        self.botones["paso"].configure(state="normal" if not self.ejecutando and (self.cpu is None or vivo) else "disabled")
        self.botones["pausar"].configure(state="normal" if self.ejecutando else "disabled")
        self.botones["retroceder"].configure(state="normal" if retrocedible and not self.ejecutando else "disabled")

    def _hacer_paso(self):
        if not self.cpu or self.cpu.detenida:
            return
        antes = self.cpu.registros.copy()
        evento = self.cpu.paso()
        if evento:
            self._dibujar_cpu(antes)
            if self.cpu.detenida:
                self._estado(f"Programa finalizado en {self.cpu.pasos} pasos. Salidas: {len(self.cpu.salidas)}.")
            else:
                self._estado(f"Línea {evento.linea}: {evento.operacion} · PC {evento.pc_anterior} → {evento.pc_siguiente}")

    def paso(self):
        if self.ejecutando:
            return
        if not self._preparar():
            return
        self.pausado_en_breakpoint = False
        self._hacer_paso()

    def ejecutar(self):
        if self.ejecutando or not self._preparar() or self.cpu.detenida:
            return
        self.ignorar_breakpoint_una_vez = self.pausado_en_breakpoint
        self.pausado_en_breakpoint = False
        self.ejecutando = True
        self.pasos_sesion = 0
        self._estado("Ejecutando… Usá Pausar o F8 para detener la simulación.")
        self._actualizar_controles()
        self.temporizador = self.after(10, self._ciclo)

    def _ciclo(self):
        self.temporizador = None
        if not self.ejecutando or not self.cpu:
            return
        linea = self.cpu.programa[self.cpu.pc].linea
        if linea in self.puntos and not self.ignorar_breakpoint_una_vez:
            self.pausar()
            self.pausado_en_breakpoint = True
            self._estado(f"Detenido antes de la línea {linea} por un punto de interrupción.")
            return
        self.ignorar_breakpoint_una_vez = False
        self._hacer_paso()
        self.pasos_sesion += 1
        if self.cpu.detenida:
            self.ejecutando = False
        elif self.pasos_sesion >= 10000:
            self.pausar()
            self._estado("Pausado tras 10 000 pasos seguidos para evitar bucles interminables.")
        if self.ejecutando:
            self.temporizador = self.after(self.velocidad.get(), self._ciclo)
        self._actualizar_controles()

    def pausar(self):
        if self.temporizador is not None:
            self.after_cancel(self.temporizador)
            self.temporizador = None
        if self.ejecutando:
            self.ejecutando = False
            self._estado("Ejecución pausada. Podés continuar, avanzar o retroceder.")
        self._actualizar_controles()

    def retroceder(self):
        if self.ejecutando or not self.cpu:
            return
        anteriores = self.cpu.registros.copy()
        if self.cpu.retroceder():
            self._dibujar_cpu(anteriores)
            self.pausado_en_breakpoint = False
            self._estado(f"Retrocediste un paso. PC = {self.cpu.pc}.")

    def reiniciar(self):
        self.pausar()
        self.cpu = None
        self.pausado_en_breakpoint = False
        self.ignorar_breakpoint_una_vez = False
        if hasattr(self, "editor"):
            self.editor.configure(state="normal")
            self._dibujar_cpu()
        self._estado("CPU y consola reiniciadas. Ya podés editar el programa.")

    def abrir(self):
        ruta = filedialog.askopenfilename(title="Abrir programa ensamblador",
                   initialdir=CARPETA, filetypes=[("Ensamblador", "*.asm"), ("Texto", "*.txt"), ("Todos", "*.*")])
        if not ruta:
            return
        try:
            codigo = Path(ruta).read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as error:
            messagebox.showerror("No se pudo abrir", str(error))
            return
        self._reemplazar_codigo(codigo)
        self.archivo_actual = Path(ruta)
        self._estado(f"Archivo abierto: {self.archivo_actual.name}")

    def guardar(self):
        ruta = filedialog.asksaveasfilename(title="Guardar código ensamblador",
                   initialdir=self.archivo_actual.parent if self.archivo_actual else CARPETA,
                   initialfile=self.archivo_actual.name if self.archivo_actual else "mi_programa.asm",
                   defaultextension=".asm", filetypes=[("Ensamblador", "*.asm"), ("Todos", "*.*")])
        if not ruta:
            return
        try:
            Path(ruta).write_text(self.editor.get("1.0", "end-1c") + "\n", encoding="utf-8")
        except OSError as error:
            messagebox.showerror("No se pudo guardar", str(error))
            return
        self.archivo_actual = Path(ruta)
        self._estado(f"Archivo guardado: {self.archivo_actual.name}")

    def ayuda(self):
        mensaje = (
            "ASM Lab · Guía rápida\n\n"
            "1. Escribí un programa o elegí un ejemplo.\n"
            "2. F7 ejecuta una instrucción a la vez.\n"
            "3. F5 ejecuta automáticamente; F8 pausa.\n"
            "4. 'Atrás' deshace el último paso ejecutado.\n"
            "5. Clic en el número de línea: agrega o quita un breakpoint.\n"
            "6. Reiniciar permite volver a editar el código.\n\n"
            "INSTRUCCIONES:\n"
            "MOV, ADD, SUB, INC, DEC, CMP, JMP, JZ, JNZ, PRINT, HLT.\n\n"
            "REGISTROS: AX, BX, CX, DX.\n"
            "BANDERAS: Z (cero) y N (negativo).\n"
            "ETIQUETA: BUCLE:  /  JMP BUCLE\n"
            "COMENTARIO: ; esto no se ejecuta.\n"
            "NÚMEROS: 10, -5, 0x10, 0b101.\n\n"
            "Este intérprete es educativo, no emula una CPU física x86."
        )
        messagebox.showinfo("Ayuda · ASM Lab", mensaje)

    def _cerrar(self):
        self.pausar()
        self.destroy()


def main():
    aplicacion = Aplicacion()
    aplicacion.mainloop()


if __name__ == "__main__":
    main()
