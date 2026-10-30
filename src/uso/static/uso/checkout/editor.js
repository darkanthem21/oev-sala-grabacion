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
  const boton = (texto, accion, desactivado = false) => {
    const b = document.createElement("button");
    b.type = "button"; b.className = "btn"; b.textContent = texto; b.disabled = desactivado;
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
  function render() {
    contenedor.replaceChildren();
    secciones.forEach((seccion, i) => {
      const tarjeta = document.createElement("section"); tarjeta.className = "checkout-seccion";
      const h = document.createElement("h3"); h.textContent = `Sección ${i + 1}`; tarjeta.append(h);
      tarjeta.append(campo("Título de la sección", seccion.titulo, 160, v => seccion.titulo = v));
      const acciones = document.createElement("div"); acciones.className = "checkout-acciones";
      acciones.append(
        boton("Subir sección", () => mover(secciones, i, -1), i === 0),
        boton("Bajar sección", () => mover(secciones, i, 1), i === secciones.length - 1),
        boton("Eliminar sección", () => { secciones.splice(i, 1); guardar(); render(); }, secciones.length === 1)
      ); tarjeta.append(acciones);
      seccion.preguntas.forEach((pregunta, j) => {
        const fila = document.createElement("div"); fila.className = "checkout-pregunta";
        fila.append(campo(`Pregunta ${j + 1} · Sí / No`, pregunta.texto, 500, v => pregunta.texto = v));
        const controles = document.createElement("div"); controles.className = "checkout-acciones";
        controles.append(
          boton("Subir pregunta", () => mover(seccion.preguntas, j, -1), j === 0),
          boton("Bajar pregunta", () => mover(seccion.preguntas, j, 1), j === seccion.preguntas.length - 1),
          boton("Eliminar pregunta", () => { seccion.preguntas.splice(j, 1); guardar(); render(); }, seccion.preguntas.length === 1)
        ); fila.append(controles); tarjeta.append(fila);
      });
      tarjeta.append(boton("Añadir pregunta", () => { seccion.preguntas.push(nuevaPregunta()); guardar(); render(); }, seccion.preguntas.length >= 30));
      contenedor.append(tarjeta);
    });
    document.getElementById("agregar-seccion").disabled = secciones.length >= 30;
  }
  datos.required = false;
  document.getElementById("editor-datos").hidden = true;
  const agregar = document.getElementById("agregar-seccion"); agregar.hidden = false;
  agregar.addEventListener("click", () => {
    secciones.push({id: id(), titulo: "Nueva sección", preguntas: [nuevaPregunta()]}); guardar(); render();
  });
  form.addEventListener("submit", () => { datos.value = JSON.stringify(secciones); });
  render();
})();
