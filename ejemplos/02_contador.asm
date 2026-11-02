; EJEMPLO 2: cuenta regresiva
; JNZ regresa a la etiqueta mientras Z sea cero.
MOV CX, 5
BUCLE:
    PRINT CX
    DEC CX
    JNZ BUCLE
PRINT 0
HLT
