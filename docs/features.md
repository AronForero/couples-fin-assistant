# Guía de uso — Bot de Finanzas Aru & Mon

Este bot vive en Telegram y te permite registrar gastos, consultar el balance del mes y conversar con él, todo escribiendo de forma natural. No hay menús ni formularios — solo manda un mensaje.

---

## Registrar un gasto

Escribe el concepto del gasto y el valor. El orden no importa.

### Ejemplos

| Lo que escribes | Lo que entiende el bot |
|---|---|
| `Supermercado 50000` | Gasto de $50.000 en supermercado, pagado por quien escribe |
| `crepes&waffles 120000` | Restaurante, $120.000 |
| `Gasolina 80000 Aru` | Aru pagó $80.000 de gasolina |
| `Mon pagó gasolina 80000` | Mon pagó $80.000 de gasolina |
| `cine 30000 compartida` | Gasto compartido (se divide entre los dos), $30.000 |
| `Mon pagó vegetales 20000, proteínas 100000. Total: $120000` | Un solo registro de $120.000 con concepto consolidado |
| `medicamento 15000 ayer` | Gasto de ayer, $15.000 |
| `arriendo 1500000 el 01/05` | Gasto con fecha específica |

### Lo que el bot deduce automáticamente

- **Quién pagó** — el que manda el mensaje. Si el mensaje menciona "Aru" o "Mon", usa esa persona.
- **Fecha** — la del mensaje. Si el mensaje dice "ayer", "el lunes", "01/07", etc., usa esa fecha.
- **Compartida** — por defecto, todos los gastos son **personales** (solo tuyos). Agrega `compartida`, `juntos`, `entre ambos`, `los dos` o `dividido` si el gasto se divide entre los dos.
- **Categoría y subcategoría** — el bot las infiere del concepto automáticamente.

### Confirmación

Después de guardar el gasto, **ambos** reciben una confirmación:

```
✅ Gasto registrado en la base de datos:
📅 Fecha: 2026-05-08
👤 Quien pagó: Mon
🏷 SubCategoría: Supermercados
📂 Categoría: ALIMENTACIÓN
📝 Concepto: supermercado
💰 Valor: $50,000
🤝 Compartida: Si
💸 Valor a pagar: $31,500
📌 Observación: Aru Debe
```

Si el gasto es personal, solo lo recibe quien lo registró.

### Cómo se divide el gasto compartido

Por defecto:
- Si **Aru** pagó → Mon le debe el **37%**
- Si **Mon** pagó → Aru le debe el **63%**

Este porcentaje puede cambiarse (ver sección más abajo).

---

## Ver el balance del mes

Escribe `Balance` para ver el resumen del mes actual. Puedes mencionar el mes que quieras.

### Ejemplos

| Lo que escribes | Resultado |
|---|---|
| `Balance` | Balance del mes actual |
| `Balance de marzo` | Balance de marzo |
| `Balance marzo` | Balance de marzo |
| `Quiero ver el resumen de abril` | Balance de abril |
| `Balance 03` | Balance de marzo |

### Qué muestra el balance

El balance tiene dos secciones: **gastos compartidos** y **tus gastos personales**.

```
📊 Resumen de Gastos — Mayo 📊

🏠 Compartidos:
  Aron pagó: $100,000
  Mon pagó:  $60,000
  Total:     $160,000

  ⚖️ Mon debe a Aron: $12,340

  📂 Categorías:
    ALIMENTACIÓN: $90,000
    ENTRETENIMIENTO: $70,000

👤 Tus gastos personales (Aron):
  Total: $50,000

  📂 Categorías:
    SALUD: $30,000
    EDUCACIÓN: $20,000
```

**Privacidad:** Cada uno ve solo sus gastos personales. Los gastos compartidos los ven ambos. La deuda se calcula únicamente sobre los gastos compartidos.

---

## Hablar con el bot

El bot no solo registra gastos — también conversa.

- **Saluda:** `hola`, `buenas`, `buenos días` — el bot te responde de forma amigable.
- **Pregúntale qué puede hacer:** `¿qué puedes hacer?` — te explica sus funciones.
- **Conversa:** Si mandas algo que no es un gasto ni una consulta de balance, el bot te responde de forma natural y te recuerda cómo puede ayudarte.

No necesitas ser formal. El bot entiende lenguaje natural en español.

---

## Cambiar el porcentaje de gastos compartidos

Puedes cambiarlos escribiendo de forma natural o usando el comando `/split`.

### Ejemplos conversacionales

| Lo que escribes | Resultado |
|---|---|
| `Cambia el split a 65 para Aru y 35 para Mon` | Aru → 65%, Mon → 35% |
| `Quiero que yo pague el 70%` (escrito por Aru) | Aru → 70%, Mon → 30% |
| `Nuevo porcentaje: Aru 60, Mon 40` | Aru → 60%, Mon → 40% |

### Con el comando directo

```
/split 65 35
```

El primer número es el porcentaje de Aru, el segundo el de Mon. Deben sumar 100.

### Qué pasa después

- Quien hizo el cambio recibe una confirmación.
- La otra persona recibe una notificación automática.
- El cambio aplica **solo a los gastos nuevos** — los anteriores no se recalculan.

---

## Acceder al dashboard

El bot genera un token de acceso para el dashboard web (próximamente).

### Cómo obtener tu token

1. Escribe `/token` al bot en Telegram.
2. El bot te responde con un token largo.
3. Copia el token y pégalo en la página de login del dashboard.

El token expira en 30 días. Cuando expire, repite el proceso con `/token`.

---

## Categorías disponibles

El bot asigna automáticamente una categoría y subcategoría a cada gasto.

| Categoría | Subcategorías |
|---|---|
| ALIMENTACIÓN | Supermercados, Mercado Plaza, Restaurantes |
| TRANSPORTE | Gasolina Carro, Transp. Público |
| VIVIENDA | Arriendo + Admin, Servicios Públicos, Internet, Servicios Técnicos Hogar, Lencería Hogar, Activos Fijos Hogar |
| SALUD | AtenciónMéd. Complementaria, Exámenes Médicos, Medicina y Suplementos |
| EDUCACIÓN | Formación Académica, Libros + E-Learning |
| ENTRETENIMIENTO | Actividades Outside, Plataformas Streaming |
| INTERESES | Pago Intereses |
| AHORRO/INVERSIÓN | Ahorro Pareja |
| IMPREVISTOS | Obsequios, Otros |

---

## Mensajes de error y qué hacer

| Mensaje del bot | Qué significa | Qué hacer |
|---|---|---|
| *"Hola. Para registrar un gasto, envía el concepto y el valor..."* | El bot no encontró un concepto y un valor en el mensaje | Incluye ambos, ej. `cine 30000` |
| *"No hay gastos registrados para ese mes."* | No hay datos en ese mes | Verifica que hayas registrado gastos en ese mes |
| *"Los porcentajes deben sumar 100."* | Los dos números del split no suman 100 | Ej. `/split 65 35` ✓ — `/split 60 50` ✗ |
| *"No entendí bien los porcentajes."* | El bot detectó que querías cambiar el split pero no pudo extraer los números | Sé más explícito, ej. `split 65 para Aru y 35 para Mon` |

---

## Acceso

El bot solo responde a Aru y Mon. Cualquier otro usuario es ignorado silenciosamente.

---

## Resumen de comandos

| Acción | Cómo hacerlo |
|---|---|
| Registrar un gasto | Escribe concepto + valor (ej. `cine 30000`) |
| Registrar gasto compartido | Escribe `compartida` o `juntos` en el mensaje (ej. `cine 30000 compartida`) |
| Ver balance del mes | `Balance` |
| Ver balance de otro mes | `Balance marzo` / `Balance de abril` |
| Cambiar el porcentaje | `Cambia el split a 70 para Aru y 30 para Mon` o `/split 70 30` |
| Obtener token del dashboard | `/token` |
| Ver mensaje de bienvenida | `/start` |
