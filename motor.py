"""Motor independiente de Tkinter para el simulador educativo ASM Lab.

Modelo intencionalmente simple: registros enteros con signo sin límite de bits.
PC representa el índice de instrucción (comienza en cero), no una dirección real.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections import deque
import re


REGISTROS = ("AX", "BX", "CX", "DX")
ARIDAD = {
    "MOV": 2, "ADD": 2, "SUB": 2, "INC": 1, "DEC": 1,
    "CMP": 2, "JMP": 1, "JZ": 1, "JNZ": 1, "PRINT": 1, "HLT": 0,
}
SALTOS = {"JMP", "JZ", "JNZ"}
DESTINOS = {"MOV", "ADD", "SUB", "INC", "DEC"}
PATRON_ETIQUETA = re.compile(r"^[A-Z_][A-Z0-9_]*$")
PATRON_NUMERO = re.compile(r"^[+-]?(?:\d+|0X[0-9A-F]+|0B[01]+)$")


class ErrorEnsamblador(ValueError):
    """Error de análisis con el número de línea original del editor."""

    def __init__(self, linea: int, mensaje: str):
        self.linea = linea
        self.mensaje = mensaje
        super().__init__(f"Línea {linea}: {mensaje}")


@dataclass(frozen=True)
class Instruccion:
    linea: int
    operacion: str
    argumentos: tuple[str, ...]
    original: str


@dataclass(frozen=True)
class Evento:
    linea: int
    operacion: str
    argumentos: tuple[str, ...]
    pc_anterior: int
    pc_siguiente: int
    salida: int | None


class CPU:
    """Analiza y ejecuta una instrucción a la vez; también permite retroceder."""

    def __init__(self, fuente: str):
        self.programa: list[Instruccion] = []
        self.etiquetas: dict[str, int] = {}
        self._compilar(fuente)
        self.reiniciar()

    def _compilar(self, fuente: str) -> None:
        for numero, texto_crudo in enumerate(fuente.splitlines(), 1):
            texto = texto_crudo.split(";", 1)[0].strip().upper()
            if not texto:
                continue

            # Se admiten varias etiquetas antes de una instrucción.
            while ":" in texto:
                etiqueta, resto = texto.split(":", 1)
                etiqueta = etiqueta.strip()
                if not PATRON_ETIQUETA.fullmatch(etiqueta):
                    raise ErrorEnsamblador(numero, "Nombre de etiqueta inválido")
                if etiqueta in self.etiquetas:
                    raise ErrorEnsamblador(numero, f"La etiqueta '{etiqueta}' está repetida")
                self.etiquetas[etiqueta] = len(self.programa)
                texto = resto.strip()
                if not texto:
                    break
            if not texto:
                continue

            fragmentos = texto.split(None, 1)
            operacion = fragmentos[0]
            if operacion not in ARIDAD:
                raise ErrorEnsamblador(numero, f"Instrucción desconocida: {operacion}")
            argumentos = tuple(x.strip() for x in fragmentos[1].split(",")) if len(fragmentos) > 1 else ()
            if len(argumentos) != ARIDAD[operacion] or any(not arg for arg in argumentos):
                raise ErrorEnsamblador(
                    numero, f"{operacion} requiere {ARIDAD[operacion]} operando(s) separados por coma"
                )
            self.programa.append(Instruccion(numero, operacion, argumentos, texto_crudo.strip()))

        # Validar todos los operandos antes de ejecutar ninguna instrucción.
        for ins in self.programa:
            args, op = ins.argumentos, ins.operacion
            if op in SALTOS:
                if not PATRON_ETIQUETA.fullmatch(args[0]) or args[0] not in self.etiquetas:
                    raise ErrorEnsamblador(ins.linea, f"La etiqueta '{args[0]}' no existe")
            else:
                if op in DESTINOS and args[0] not in REGISTROS:
                    raise ErrorEnsamblador(ins.linea, "El destino debe ser AX, BX, CX o DX")
                for argumento in args:
                    if argumento not in REGISTROS and not PATRON_NUMERO.fullmatch(argumento):
                        raise ErrorEnsamblador(ins.linea, f"Operando inválido: {argumento}")

    def reiniciar(self) -> None:
        self.registros = {nombre: 0 for nombre in REGISTROS}
        self.z = False
        self.n = False
        self.pc = 0
        self.detenida = not bool(self.programa)
        self.pasos = 0
        self.ultima_linea: int | None = None
        self.salidas: list[int] = []
        self.historial: deque[tuple] = deque(maxlen=2000)
        self.eventos: deque[Evento] = deque(maxlen=300)

    def _valor(self, argumento: str) -> int:
        if argumento in self.registros:
            return self.registros[argumento]
        if argumento.lstrip("+-").startswith("0X"):
            return int(argumento, 16)
        if argumento.lstrip("+-").startswith("0B"):
            return int(argumento, 2)
        return int(argumento, 10)

    def paso(self) -> Evento | None:
        if self.detenida:
            return None
        ins = self.programa[self.pc]
        self.historial.append((
            self.pc, self.registros.copy(), self.z, self.n,
            self.detenida, self.pasos, self.ultima_linea, len(self.salidas),
        ))
        previo = self.pc
        siguiente = previo + 1
        args, op = ins.argumentos, ins.operacion
        resultado = None
        salida = None

        if op == "MOV":
            self.registros[args[0]] = self._valor(args[1])
        elif op in {"ADD", "SUB", "INC", "DEC"}:
            cantidad = self._valor(args[1]) if len(args) == 2 else 1
            signo = 1 if op in {"ADD", "INC"} else -1
            resultado = self.registros[args[0]] + signo * cantidad
            self.registros[args[0]] = resultado
        elif op == "CMP":
            resultado = self._valor(args[0]) - self._valor(args[1])
        elif op in SALTOS:
            if op == "JMP" or (op == "JZ" and self.z) or (op == "JNZ" and not self.z):
                siguiente = self.etiquetas[args[0]]
        elif op == "PRINT":
            salida = self._valor(args[0])
            self.salidas.append(salida)
        elif op == "HLT":
            self.detenida = True

        if resultado is not None:
            self.z = resultado == 0
            self.n = resultado < 0
        self.pc = siguiente
        self.pasos += 1
        self.ultima_linea = ins.linea
        self.detenida = self.detenida or self.pc >= len(self.programa)
        evento = Evento(ins.linea, op, args, previo, siguiente, salida)
        self.eventos.append(evento)
        return evento

    def retroceder(self) -> bool:
        """Vuelve al estado inmediatamente anterior, incluida la consola."""
        if not self.historial:
            return False
        (self.pc, self.registros, self.z, self.n,
         self.detenida, self.pasos, self.ultima_linea, longitud) = self.historial.pop()
        del self.salidas[longitud:]
        if self.eventos:
            self.eventos.pop()
        return True
