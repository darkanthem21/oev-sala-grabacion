// Editor de secciones y preguntas del check-out.
(() => {
  const form = document.getElementById("editor-checkout");
  if (!form) return;
  const datos = document.getElementById("id_secciones");
  const contenedor = document.getElementById("editor-secciones");
  const estado = document.getElementById("editor-estado");
  let secciones;
  try {
    secciones = JSON.parse(datos.value);
    if (!Array.isArray(secciones) || !secciones.every(s => typeof s.titulo === "string" && Array.isArray(s.preguntas) && s.preguntas.every(p => typeof p.texto === "string"))) return;
  } catch { return; }
  const id = () => "id_" + Array.from(crypto.getRandomValues(new Uint8Array(16)), b => b.toString(16).padStart(2, "0")).join("");
  const guardar = () => { datos.value = JSON.stringify(secciones); estado.textContent = "Cambios sin publicar."; };
  const boton = (texto, accion, desactivado = false, estilo = "", etiqueta = texto) => {
    const b = document.createElement("button");
    b.type = "button"; b.className = `btn ${estilo}`; b.textContent = texto; b.disabled = desactivado;
    b.setAttribute("aria-label", etiqueta);
    b.addEventListener("click", accion);
    return b;
  };
  const mover = (lista, indice, cambio) => {
    [lista[indice], lista[indice + cambio]] = [lista[indice + cambio], lista[indice]];
    guardar(); render();
  };
  const campo = (etiqueta, valor, limite, cambiar) => {
    const label = document.createElement("label"); label.textContent = etiqueta;
    const input = document.createElement("input"); input.type = "text"; input.required = true;
    input.maxLength = limite; input.value = valor;
    input.addEventListener("input", () => { cambiar(input.value); guardar(); });
    label.append(input); return label;
  };
  const nuevaPregunta = () => ({id: id(), texto: ""});
  function render(enfoque = null) {
    contenedor.replaceChildren();
    secciones.forEach((seccion, i) => {
      const tarjeta = document.createElement("section"); tarjeta.className = "checkout-seccion";
      const cabecera = document.createElement("div"); cabecera.className = "checkout-seccion-cabecera";
      const h = document.createElement("h3"); h.textContent = `Sección ${i + 1}`; cabecera.append(h);
      const acciones = document.createElement("div"); acciones.className = "checkout-orden";
      acciones.setAttribute("role", "group"); acciones.setAttribute("aria-label", `Organizar sección ${i + 1}`);
      acciones.append(
        boton("↑ Subir", () => mover(secciones, i, -1), i === 0, "checkout-btn-orden", `Subir sección ${i + 1}`),
        boton("↓ Bajar", () => mover(secciones, i, 1), i === secciones.length - 1, "checkout-btn-orden", `Bajar sección ${i + 1}`),
        boton("Eliminar sección", () => { secciones.splice(i, 1); guardar(); render(); }, secciones.length === 1, "checkout-btn-eliminar")
      ); cabecera.append(acciones); tarjeta.append(cabecera);
      tarjeta.append(campo("Título de la sección", seccion.titulo, 160, v => seccion.titulo = v));
      seccion.preguntas.forEach((pregunta, j) => {
        const fila = document.createElement("div"); fila.className = "checkout-pregunta checkout-editor-pregunta";
        fila.append(campo(`Pregunta ${j + 1} · Sí / No`, pregunta.texto, 500, v => pregunta.texto = v));
        const controles = document.createElement("div"); controles.className = "checkout-orden checkout-orden-pregunta";
        controles.setAttribute("role", "group"); controles.setAttribute("aria-label", `Organizar pregunta ${j + 1} de la sección ${i + 1}`);
        controles.append(
          boton("↑ Subir", () => mover(seccion.preguntas, j, -1), j === 0, "checkout-btn-orden", `Subir pregunta ${j + 1} de la sección ${i + 1}`),
          boton("↓ Bajar", () => mover(seccion.preguntas, j, 1), j === seccion.preguntas.length - 1, "checkout-btn-orden", `Bajar pregunta ${j + 1} de la sección ${i + 1}`),
          boton("Eliminar pregunta", () => { seccion.preguntas.splice(j, 1); guardar(); render(); }, seccion.preguntas.length === 1, "checkout-btn-eliminar")
        ); fila.append(controles); tarjeta.append(fila);
        if (enfoque === pregunta.id) requestAnimationFrame(() => fila.querySelector("input").focus());
      });
      const pie = document.createElement("div"); pie.className = "checkout-pie-seccion";
      pie.append(boton("+ Añadir pregunta a esta sección", () => {
        const pregunta = nuevaPregunta(); seccion.preguntas.push(pregunta); guardar(); render(pregunta.id);
      }, seccion.preguntas.length >= 30, "checkout-btn-pregunta"));
      tarjeta.append(pie);
      contenedor.append(tarjeta);
      if (enfoque === seccion.id) requestAnimationFrame(() => tarjeta.querySelector("input").focus());
    });
    document.getElementById("agregar-seccion").disabled = secciones.length >= 30;
  }
  datos.required = false;
  document.getElementById("editor-datos").hidden = true;
  const agregar = document.getElementById("agregar-seccion");
  document.getElementById("agregar-seccion-panel").hidden = false;
  agregar.addEventListener("click", () => {
    const seccion = {id: id(), titulo: "Nueva sección", preguntas: [nuevaPregunta()]};
    secciones.push(seccion); guardar(); render(seccion.id);
  });
  form.addEventListener("submit", () => { datos.value = JSON.stringify(secciones); });
  render();
})();
