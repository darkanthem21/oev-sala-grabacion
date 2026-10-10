/* Avisos flotantes, pop-ups anclados y diálogos (estilos en css/flotantes.css).
 * Sin dependencias, porque lo cargan también las páginas sin Alpine. Expone
 * avisar(), anclar() y sacudir() en window. */
(function () {
  const quieto = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  const angosto = () => matchMedia("(max-width: 40rem)").matches;

  // --- Avisos ---
  // Escuchados desde document y no desde cada aviso: al volver con Atrás htmx
  // reemplaza el <body> entero, y lo enganchado a #avisos se iría con él. Sirve
  // igual para los que dibuja el servidor, los que llegan fuera de banda y los
  // de avisar().
  function retirar(aviso) {
    if (quieto()) aviso.remove();
    else aviso.classList.add("sale");
  }

  // El reloj es la animación de la barra (::after), que el CSS pausa con mouse o foco.
  document.addEventListener("animationend", (e) => {
    const aviso = e.target.closest?.(".aviso-flotante");
    if (e.animationName === "aviso-tiempo") retirar(aviso);
    if (e.animationName === "aviso-sale") aviso.remove();
  });
  document.addEventListener("click", (e) => {
    const cerrar = e.target.closest?.(".aviso-flotante .cerrar");
    if (cerrar) retirar(cerrar.closest(".aviso-flotante"));
  });

  window.avisar = function (texto, tipo = "hecho") {
    const aviso = document.createElement("div");
    aviso.className = "aviso-flotante " + tipo;
    if (tipo === "error") aviso.setAttribute("role", "alert");
    aviso.innerHTML = '<span class="texto"></span><button type="button" class="cerrar" aria-label="Cerrar aviso">×</button>';
    aviso.querySelector(".texto").textContent = texto;
    document.getElementById("avisos").append(aviso);
  };

  // --- Pop-ups anclados ---
  const MARGEN = 8;

  // A la derecha de lo que se tocó; si no cabe, a la izquierda; si tampoco,
  // debajo. Sin ancla, centrado. En el celular lo ubica el CSS (hoja).
  function ubicar(el) {
    if (!el.matches(":popover-open") || angosto()) { el.style.left = el.style.top = ""; return; }
    const w = el.offsetWidth, h = el.offsetHeight, ancho = innerWidth, alto = innerHeight;
    const r = el._ancla?.isConnected ? el._ancla.getBoundingClientRect() : null;
    let left, top;
    if (!r) {
      left = (ancho - w) / 2; top = (alto - h) / 3;
    } else {
      left = r.right + MARGEN; top = r.top;
      if (left + w > ancho - MARGEN) left = r.left - w - MARGEN;
      if (left < MARGEN) {
        left = Math.min(Math.max(r.left, MARGEN), ancho - w - MARGEN);
        top = r.bottom + MARGEN;
      }
    }
    el.style.left = Math.max(left, MARGEN) + "px";
    el.style.top = Math.min(Math.max(top, MARGEN), alto - h - MARGEN) + "px";
  }

  // Abre o cierra `el` (un [popover="manual"]) junto a `ancla`. Quien llama
  // es dueño del estado; acá solo se dibuja. Al abrir, el foco va al primer
  // campo, que es por donde sigue quien usa el teclado.
  window.anclar = function (el, ancla, abierto) {
    if (!abierto) {
      if (el.matches(":popover-open")) el.hidePopover();
      return;
    }
    el._ancla = ancla;
    if (!el.matches(":popover-open")) {
      el.showPopover();
      el.querySelector("input:not([type=hidden]):not([disabled]), select:not([disabled]), textarea")?.focus({ preventScroll: true });
    }
    ubicar(el);
  };

  window.sacudir = function (el) {
    if (quieto()) return;
    el.classList.remove("sacude");
    void el.offsetWidth;
    el.classList.add("sacude");
    el.addEventListener("animationend", () => el.classList.remove("sacude"), { once: true });
  };

  const reubicar = () => document.querySelectorAll(".flotante:popover-open").forEach(ubicar);
  addEventListener("resize", reubicar);
  addEventListener("scroll", reubicar, true);

  // --- Diálogos ---
  // Un botón con data-abre="id" abre ese <dialog>; se cierra con Esc, con un
  // <form method="dialog"> o con un clic en el fondo.
  document.addEventListener("click", (e) => {
    const boton = e.target.closest?.("[data-abre]");
    if (boton) { document.getElementById(boton.dataset.abre)?.showModal(); return; }
    const dialogo = e.target;
    if (dialogo.matches?.("dialog.dialogo[open]")) {
      const r = dialogo.getBoundingClientRect();
      if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) dialogo.close();
    }
  });
})();
