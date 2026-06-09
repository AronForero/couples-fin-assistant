# FinDuo — Guía de uso

FinDuo es tu asistente personal de finanzas. Tiene dos caras:

- **Bot de Telegram** — registra gastos e ingresos escribiendo en lenguaje natural.
- **Dashboard web** — visualiza, edita y gestiona todo desde el navegador.

No hay formularios complicados, ni menús. Escribes como hablarías y el bot entiende.

---

## Tabla de contenidos

1. [Empezar](#empezar)
2. [Telegram Bot](#telegram-bot)
   - [Cuenta y vinculación](#cuenta-y-vinculación)
   - [Registrar un gasto](#registrar-un-gasto)
   - [Registrar un ingreso](#registrar-un-ingreso)
   - [Ver el balance del mes](#ver-el-balance-del-mes)
   - [Ver gastos recientes](#ver-gastos-recientes)
   - [Editar un gasto o ingreso](#editar-un-gasto-o-ingreso)
   - [Eliminar un gasto o ingreso](#eliminar-un-gasto-o-ingreso)
   - [Cambiar el porcentaje de gastos compartidos](#cambiar-el-porcentaje-de-gastos-compartidos)
   - [Salir de la pareja](#salir-de-la-pareja)
   - [Conversar con el bot](#conversar-con-el-bot)
3. [Dashboard Web](#dashboard-web)
   - [Acceso](#acceso)
   - [Estado de cuenta](#estado-de-cuenta)
   - [Página de balance](#página-de-balance)
   - [Página de transacciones](#página-de-transacciones)
   - [Gestión de pareja](#gestión-de-pareja)
   - [Parejas anteriores](#parejas-anteriores)
   - [Invitar pareja](#invitar-pareja)
4. [Categorías de gastos](#categorías-de-gastos)
5. [Cómo se divide un gasto compartido](#cómo-se-divide-un-gasto-compartido)
6. [Resumen de comandos](#resumen-de-comandos)
7. [Mensajes de error](#mensajes-de-error)

---

## Empezar

1. Crea tu cuenta en el dashboard web (botón "Registrarse").
2. Si querés usar el bot de Telegram, vincula tu cuenta con `/link tu@email.com` en el chat con el bot.
3. Empezás con un **trial gratuito de 30 días** con acceso completo.
4. Pasado ese tiempo, necesitás una cuenta paga para seguir usando el bot (el dashboard sigue accesible en modo lectura).

---

# Telegram Bot

## Cuenta y vinculación

| Lo que escribes | Resultado |
|---|---|
| `/start` | Mensaje de bienvenida con ejemplos según si estás en pareja o no |
| `/link tu@email.com` | Vincula tu cuenta de Telegram con tu cuenta del dashboard |

Si no estás vinculado, el bot te avisa y no responde a otros mensajes.

---

## Registrar un gasto

Escribí el concepto y el valor. El orden no importa. El bot deduce el resto.

### Ejemplos

| Lo que escribes | Lo que entiende el bot |
|---|---|
| `Supermercado 50000` | Gasto de $50.000, pagado por quien escribe |
| `crepes&waffles 120000` | Restaurante, $120.000 |
| `Gasolina 80000 Aru` | Aru pagó $80.000 de gasolina |
| `Mon pagó gasolina 80000` | Mon pagó $80.000 de gasolina |
| `cine 30000 compartida` | Gasto compartido, $30.000 |
| `Mon pagó vegetales 20000, proteínas 100000. Total: $120000` | Un solo registro de $120.000 |
| `medicamento 15000 ayer` | Gasto de ayer, $15.000 |
| `arriendo 1500000 el 01/05` | Gasto con fecha específica |

### Lo que el bot deduce automáticamente

- **Quién pagó** — el que manda el mensaje. Si decís "Aru" o "Mon", usa esa persona.
- **Fecha** — la del mensaje. Si decís "ayer", "el lunes", "01/07", usa esa fecha.
- **Compartida** — por defecto es **personal** (solo tuyo). Agregá `compartida`, `juntos`, `entre ambos`, `los dos` o `dividido` si se divide entre los dos.
- **Categoría y subcategoría** — el bot las infiere del concepto.

### Confirmación

Después de guardar, **ambos** reciben una confirmación (o solo vos si es personal):

```
✅ Gasto #42 registrado:
📅 Fecha: 2026-05-08
👤 Quien pagó: Mon
🏷 SubCategoría: Supermercados
📂 Categoría: ALIMENTACIÓN
📝 Concepto: supermercado
💰 Valor: $50,000
🤝 Compartida: Si
💸 Valor a pagar: $31,500
```

---

## Registrar un ingreso

Además de gastos, podés registrar dinero que recibís — salario, freelance, utilidades, etc. Es **personal**, no se comparte con tu pareja.

### Ejemplos

| Lo que escribes | Lo que entiende el bot |
|---|---|
| `Salario 2000000` | Ingreso de $2.000.000, concepto "Salario" |
| `Ingreso freelance 1500000` | Ingreso freelance, $1.500.000 |
| `Recibí utilidades panaderia 3500000` | Ingreso de utilidades, $3.500.000 |
| `Cobré venta de bicicleta 800000` | Ingreso de venta, $800.000 |
| `Honorarios 1200000 ayer` | Ingreso de ayer, $1.200.000 |

### Palabras clave reconocidas

El bot identifica ingresos cuando el mensaje contiene alguna de estas palabras:

`salario`, `ingreso`, `ingresos`, `recibí`, `gané`, `cobré`, `utilidades`, `honorarios`, `freelance`, `venta`, `pago recibido`.

### Confirmación

```
✅ Ingreso #5 registrado:
📅 Fecha: 2026-06-07
👤 Recibido por: Aru
📝 Concepto: Salario
💰 Valor: $2,000,000
```

> 💡 Las **calculaciones de dinero real** (ingresos menos gastos) vienen en una versión futura. Por ahora solo se registra la lista.

---

## Ver el balance del mes

Escribí `Balance` para ver el resumen del mes actual. Podés mencionar otro mes.

| Lo que escribes | Resultado |
|---|---|
| `Balance` | Balance del mes actual |
| `Balance de marzo` | Balance de marzo |
| `Balance 03` | Balance de marzo |
| `Quiero ver el resumen de abril` | Balance de abril |

### Qué muestra el balance

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

**Privacidad:** cada uno ve solo sus gastos personales. Los compartidos los ven ambos. La deuda se calcula solo sobre los compartidos.

> ⚠️ Si no estás en una pareja, el bot te avisa que no podés ver balance (los ingresos y gastos personales sí funcionan).

---

## Ver gastos recientes

Para ver tus últimos gastos con sus IDs (útil para editar o eliminar):

| Lo que escribes | Resultado |
|---|---|
| `últimos gastos` | Últimos 5 gastos |
| `gastos recientes` | Últimos 5 gastos |
| `últimos 10 gastos` | Últimos 10 gastos |
| `/last` | Últimos 5 gastos |
| `/last 15` | Últimos 15 gastos |

---

## Editar un gasto o ingreso

Si te equivocaste, podés corregirlo indicando el ID y lo que querés cambiar.

### Cómo saber el ID

- Aparece en la confirmación cuando registrás un gasto o ingreso (ej. `Gasto #42 registrado`).
- También podés verlos con `últimos gastos` o `/last`.

### Ejemplos para gastos

| Lo que escribes | Resultado |
|---|---|
| `editar gasto 42, era compartido` | Marca el gasto #42 como compartido |
| `gasto 42, el valor era 25000` | Cambia el valor a $25.000 |
| `corregir gasto 38, pagó Mon` | Cambia quién pagó a Mon |
| `editar gasto 42, concepto verduras del mercado, compartida` | Cambia concepto y marca como compartido |

### Ejemplos para ingresos

| Lo que escribes | Resultado |
|---|---|
| `editar ingreso 7, el valor era 2500000` | Cambia el valor del ingreso a $2.500.000 |
| `corregir ingreso 7, concepto Salario quincena` | Cambia el concepto |

### Campos editables

- **Gastos:** valor, concepto, fecha, compartida, quien_pago, categoría, subcategoría
- **Ingresos:** valor, concepto, fecha

Solo mencioná los campos que querés cambiar — los demás se mantienen.

### Qué pasa después

- Si cambiás el valor, quién pagó, o si es compartido, el bot recalcula la deuda.
- Si el gasto es compartido, **ambos** reciben la confirmación con los datos actualizados.
- Los ingresos son personales — solo vos recibís la confirmación.

---

## Eliminar un gasto o ingreso

Indicá el ID y el tipo:

| Lo que escribes | Resultado |
|---|---|
| `eliminar gasto 42` | Elimina el gasto #42 |
| `borrar gasto 38` | Elimina el gasto #38 |
| `eliminar ingreso 7` | Elimina el ingreso #7 |
| `borrar el ingreso 12` | Elimina el ingreso #12 |

> Si el gasto era compartido, **ambos** reciben una notificación de la eliminación.

---

## Cambiar el porcentaje de gastos compartidos

Podés cambiarlo escribiendo de forma natural o usando el comando `/split`.

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

## Salir de la pareja

Si querés terminar la pareja financiera actual, podés hacerlo desde el **dashboard** (botón "Salir de la pareja" en `/couple/manage`) o escribí en el bot algo como `quiero salir de la pareja`. El bot te guiará.

**Importante:**
- Al salir, **ambos** quedan marcados como salidos — la pareja se vuelve histórica inmediatamente.
- Tu pareja recibe una notificación por Telegram.
- Los gastos de esa pareja siguen visibles en el dashboard bajo "Parejas anteriores".
- Después podés crear o unirte a una nueva pareja.

---

## Conversar con el bot

El bot no solo registra gastos — también conversa.

- **Saluda:** `hola`, `buenas`, `buenos días` — responde con amabilidad.
- **Preguntale qué puede hacer:** `¿qué puedes hacer?` — te explica sus funciones.
- **Conversa:** si mandás algo que no es un gasto, ingreso, balance, edición o eliminación, el bot responde naturalmente y te recuerda sus funciones.

No necesitás ser formal. El bot entiende lenguaje natural en español.

---

# Dashboard Web

## Acceso

1. Abrí el dashboard en el navegador.
2. Ingresá tu email y contraseña.
3. Listo — ya podés ver y gestionar tus finanzas.

Si no tenés cuenta, hace clic en "Registrarse" desde la pantalla de login.

---

## Estado de cuenta

El estado de tu cuenta se muestra siempre en un banner arriba de la barra de navegación:

| Estado | Banner | Significado |
|---|---|---|
| **Trial** | 🟡 Amarillo: *"Modo de prueba — X días restantes"* | Primeros 30 días desde el registro. Acceso total. |
| **Activo** | (sin banner) | Cuenta paga. Acceso total. |
| **Suspendido** | 🟠 Coral: *"Tu cuenta está suspendida. Completa tu pago para continuar."* | Pago rechazado. El bot está bloqueado, pero podés ver tu dashboard en modo lectura. |

> 💳 La integración de pagos (Wompi) se implementará en una versión futura. Por ahora el estado solo se puede cambiar manualmente desde la base de datos.

---

## Página de balance (`/balance`)

Muestra el resumen del mes actual para tu pareja activa.

- **Gastos compartidos** — quién pagó, total, deuda, desglose por categoría.
- **Gastos personales** — tu total personal y desglose por categoría.
- **Selector de mes** — elegí cualquier mes.
- **Selector de pareja** (dropdown) — si tuviste parejas anteriores, podés ver el balance de cada una.

---

## Página de transacciones (`/expenses`)

Lista unificada de gastos e ingresos del mes seleccionado.

### Filtros

Tres botones arriba a la derecha:

- **Todos** — muestra gastos e ingresos juntos (default)
- **Gastos** — solo gastos
- **Ingresos** — solo ingresos

### Tarjetas de resumen

Cuatro tarjetas arriba de la lista:

- **Total gastos** — suma de todos los gastos del mes
- **Total ingresos** — suma de todos los ingresos (en verde)
- **Gastos compartidos** — cantidad de gastos marcados como compartidos
- **Gastos personales** — cantidad de gastos no compartidos

### Edición de gastos

- Click en el ícono de editar de una fila para abrir el modal de edición.
- Podés cambiar: fecha, valor, concepto, categoría, quién pagó, compartida.
- El modal tiene un botón para **eliminar** el gasto (con confirmación).

### Ingresos

- Los ingresos se muestran en verde con un signo `+` adelante.
- Por ahora son de **solo lectura** en el dashboard — para editarlos o eliminarlos, usá el bot.

### Modo lectura

Si tu cuenta está **suspendida**:
- No podés editar ni eliminar gastos.
- El botón "Salir de la pareja" también está deshabilitado.
- Todo lo demás se puede ver normalmente.

---

## Gestión de pareja (`/couple/manage`)

- **Pareja actual** — si tenés, muestra el nombre de tu pareja, el total gastado juntos, y un botón **"Salir de la pareja"** (con confirmación).
- **Parejas anteriores** — si tuviste parejas previas, aparecen como tarjetas con el nombre de la ex-pareja, fechas y total gastado. Click en una para ver sus gastos.

---

## Parejas anteriores (`/couple/[id]/expenses`)

Vista de solo lectura de todos los gastos de una pareja anterior. Tiene selector de mes para filtrar.

---

## Invitar pareja (`/invite`)

- Si no tenés pareja activa, esta página te muestra el **código de invitación** para crear una nueva pareja.
- Después de salir de una pareja, esta página te da orientación para empezar de nuevo.

---

# Categorías de gastos

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

Los ingresos **no tienen categorías** — solo concepto, valor y fecha.

---

# Cómo se divide un gasto compartido

Por defecto:
- Si **Aru** pagó → Mon le debe el **37%**
- Si **Mon** pagó → Aru le debe el **63%**

Este porcentaje se cambia con `/split` o en lenguaje natural (ver arriba). Aplica solo a gastos nuevos.

---

# Resumen de comandos

## Bot de Telegram

| Acción | Cómo hacerlo |
|---|---|
| Ver bienvenida | `/start` |
| Vincular cuenta | `/link email@ejemplo.com` |
| Registrar gasto | `concepto valor` (ej. `cine 30000`) |
| Gasto compartido | Agregar `compartida` al mensaje |
| Registrar ingreso | Incluir palabra clave + valor (ej. `Salario 2000000`) |
| Ver balance del mes | `Balance` |
| Balance de otro mes | `Balance marzo` o `Balance de abril` |
| Ver últimos gastos | `últimos gastos` o `/last` |
| Editar gasto | `editar gasto 42, era compartido` |
| Editar ingreso | `editar ingreso 7, el valor era 2500000` |
| Eliminar gasto | `eliminar gasto 42` |
| Eliminar ingreso | `borrar ingreso 7` |
| Cambiar porcentaje | `Cambia el split a 70 para Aru y 30 para Mon` o `/split 70 30` |
| Salir de la pareja | `quiero salir de la pareja` (o desde el dashboard) |

## Dashboard Web

| Acción | Dónde |
|---|---|
| Ver balance del mes | `/balance` |
| Ver y editar transacciones | `/expenses` |
| Gestionar pareja | `/couple/manage` |
| Ver gastos de pareja anterior | `/couple/[id]/expenses` |
| Invitar o crear pareja | `/invite` |
| Ver estado de cuenta | Banner en la barra superior |

---

# Mensajes de error

| Mensaje del bot | Qué significa | Qué hacer |
|---|---|---|
| *"Tu cuenta está suspendida. Completa tu pago para continuar."* | Tu cuenta fue suspendida (pago rechazado) | Actualizá tu método de pago |
| *"Para registrar un gasto, envía el concepto y el valor..."* | El bot no encontró un concepto y un valor | Incluí ambos, ej. `cine 30000` |
| *"Para registrar un ingreso, envialo con un monto..."* | El bot no encontró un valor en el ingreso | Incluí un número, ej. `Salario 2000000` |
| *"No hay gastos registrados para ese mes."* | No hay datos en ese mes | Verificá que hayas registrado gastos en ese mes |
| *"Los porcentajes deben sumar 100."* | Los dos números del split no suman 100 | Usá `/split 65 35` (suma 100) |
| *"No entendí bien los porcentajes."* | El bot detectó que querías cambiar el split pero no pudo extraer los números | Sé más explícito, ej. `split 65 para Aru y 35 para Mon` |
| *"Gasto #42 no encontrado"* | El ID que mencionaste no existe | Verificá el ID con `últimos gastos` o `/last` |
| *"No tenés pareja. Creá una desde la web para..."* | Intentaste hacer algo que requiere pareja (balance, gasto compartido) | Creá o unite a una pareja desde `/invite` |
| *"Ya estás vinculado como X."* | Intentaste vincular dos veces | No necesitás volver a vincular |
