# Estilo

Del **Manual de marca de la Facultad de Ciencias de la Ingeniería (UACh)**.
Los valores y el porqué de cada uno están en `src/static/css/marca.css`.

El editor y el reporte del check-out usan estos tokens en
`src/uso/static/uso/checkout/checkout.css`: Montserrat Bold para títulos,
Roboto para etiquetas y controles, azul de acción y turquesa institucional
para botones y bordes. Los errores se muestran con texto oscuro sobre el
relleno naranja de aviso; el naranja no se usa como texto sobre blanco.

Las pestañas Formulario/Historial y las semanas usan los mismos tokens de marca.
La confirmación de publicación es una ventana modal de la página (`dialog`), con
título Montserrat Bold y texto Roboto. Tiene formato de alerta compacta, esquinas
redondeadas, borde fino naranja e indicador de advertencia. El botón de confirmar
usa naranja suavizado con texto oscuro; el celeste queda en el botón secundario.
Reutiliza los tokens de marca y permite cancelar con Seguir editando o Escape.
El PDF incorpora el identificador gráfico de la Facultad y usa Montserrat Bold
y Roboto Regular desde `src/uso/checkout/fonts/`, cuyas licencias se distribuyen
junto a las fuentes. Los colores del documento se leen de `marca.css`.

## Tipografías

| Uso | Fuente |
|---|---|
| Encabezados | Montserrat Bold |
| Párrafos | Roboto Regular |

Las sirve la app desde `src/static/fonts/` (subconjunto latino, licencia OFL).

## Colores del manual

| | | | | | |
|---|---|---|---|---|---|
| `#516e80` | `#dbd5d0` | `#dd5829` | `#e3994c` | `#aebe4c` | `#9ec089` |
| `#68abc2` | `#0097a6` | `#006699` | `#954f72` | `#ebf7fc` | `#2a4451` |

El manual trae aparte dos Pantone: **320 C**, que es `#0097a6`, y **Orange 021 C**,
que el propio PDF define como `#e15200`. El `#dd5829` de la grilla es otro color.

## Reparto en la app

| Papel | Color | Contraste |
|---|---|---|
| Marca: banda del encabezado, botón principal, pestaña activa, subrayado de links | `#e15200` (021 C) | Blanco encima 3.88:1: solo texto de 20 px en negrita o más |
| Texto, botones y links de texto chico | `#2a4451` | 10.3:1 sobre blanco |
| Texto secundario y borde de campos | `#516e80` | 5.4:1 |
| Fondo | Blanco, con filetes `#dbd5d0` | |
| Error, rechazada, tope, bloqueado | `#954f72` | 5.8:1 |
| Precaución, éxito, información (solo filetes junto a un texto) | `#e3994c`, `#aebe4c`, `#68abc2` | |

| Rol (US-08 AC7) | Color | Ícono |
|---|---|---|
| Solicitante | `#e15200` | calendar-plus |
| Validador | `#0097a6` (320 C) | badge-check |
| Administrador | `#2a4451` | settings |
| Personal de apoyo | `#516e80` | clapperboard |

Los íconos son de [Lucide](https://lucide.dev) (licencia ISC), en `src/static/img/roles/`.

## Reglas de uso

- **Tocar:** con el dedo (`pointer: coarse`) todo control mide 44 px de alto; con
  mouse, 36. Sale de `--alto-control`, no se fija por pantalla.
- **Encabezados de tabla y rótulos:** en minúscula, sin `text-transform`. Las
  mayúsculas sostenidas se leen peor y no eran parejas entre pantallas.
- **Deshabilitado:** borde claro y texto secundario, sin opacidad: tiene que
  poder leerse qué es lo que todavía no se puede hacer.
- **Celular:** las pestañas van en una fila que se desliza; el botón principal
  parte su rótulo en dos líneas antes que ensanchar la página.
- **Título de la pestaña del navegador:** el de la pantalla, no el del panel
  (`Usuarios · Configuración`), para distinguir pestañas e historial.
