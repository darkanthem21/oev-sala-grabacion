# Estilo

Del **Manual de marca de la Facultad de Ciencias de la Ingeniería (UACh)**.
Los valores y el porqué de cada uno están en `src/static/css/marca.css`.

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
