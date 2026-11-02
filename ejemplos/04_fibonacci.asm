; EJEMPLO 4: primeros 8 números de Fibonacci
; AX: término anterior, BX: término actual
; DX: auxiliar, CX: repeticiones
MOV AX, 0
MOV BX, 1
MOV CX, 8
CICLO:
    PRINT AX
    MOV DX, AX
    ADD DX, BX
    MOV AX, BX
    MOV BX, DX
    DEC CX
    JNZ CICLO
HLT
