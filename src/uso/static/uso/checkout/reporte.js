// La validación definitiva se ejecuta también en el servidor.
document.querySelectorAll(".checkout-pregunta").forEach(pregunta => {
  const evidencia = pregunta.querySelector(".checkout-evidencia");
  if (!evidencia) return;
  function actualizar() {
    const incumple = pregunta.querySelector('input[type="radio"]:checked')?.value === "no";
    evidencia.hidden = !incumple;
    evidencia.querySelectorAll("textarea, input").forEach(campo => {
      campo.required = incumple && campo.dataset.conservada !== "si";
      campo.disabled = !incumple;
      if (campo.name.startsWith("observacion_")) campo.minLength = 10;
    });
  }
  pregunta.querySelectorAll('input[type="radio"]').forEach(radio => radio.addEventListener("change", actualizar));
  actualizar();
});

const asistenciaForm = document.getElementById("asistencia-form");
if (asistenciaForm) {
  const boton = document.getElementById("continuar-asistencia");
  const actualizarAsistencia = () => {
    const noAsistio = asistenciaForm.querySelector('input[name="asistencia"]:checked')?.value === "no";
    const preview = Boolean(asistenciaForm.querySelector('input[name="secciones"]'));
    boton.textContent = noAsistio ? (preview ? "Probar inasistencia" : "Registrar inasistencia") : "Continuar al listado";
    if (preview) boton.value = noAsistio ? "probar" : "asistencia";
  };
  asistenciaForm.addEventListener("change", actualizarAsistencia);
  actualizarAsistencia();
}

const listadoAsistencia = document.getElementById("listado-asistencia");
if (listadoAsistencia) {
  const formulario = listadoAsistencia.closest("form");
  const actualizar = () => {
    const asistio = formulario.querySelector('input[name="asistencia"]:checked')?.value === "si";
    listadoAsistencia.hidden = !asistio;
    listadoAsistencia.disabled = !asistio;
  };
  formulario.querySelectorAll('input[name="asistencia"]').forEach(campo => campo.addEventListener("change", actualizar));
  actualizar();
}

document.querySelectorAll(".checkout-carga").forEach(carga => {
  const campo = carga.querySelector('input[type="file"]');
  const figura = carga.querySelector("figure");
  const imagen = figura.querySelector("img");
  const estado = carga.querySelector(".checkout-archivo-estado");
  let url = null;
  const limpiar = () => {
    if (url) URL.revokeObjectURL(url);
    url = null; figura.hidden = true; imagen.removeAttribute("src");
  };
  campo.addEventListener("change", () => {
    limpiar(); estado.textContent = ""; campo.setCustomValidity("");
    const archivo = campo.files[0];
    if (!archivo) return;
    if (archivo.size > 5 * 1024 * 1024 || !["image/jpeg", "image/png", "image/webp"].includes(archivo.type)) {
      const mensaje = "Selecciona una imagen JPEG, PNG o WebP de hasta 5 MB.";
      campo.setCustomValidity(mensaje); estado.textContent = mensaje; return;
    }
    imagen.onload = () => { figura.hidden = false; };
    imagen.onerror = () => { limpiar(); estado.textContent = "No se pudo mostrar esta imagen. Selecciona otra fotografía."; campo.setCustomValidity(estado.textContent); };
    url = URL.createObjectURL(archivo); imagen.src = url;
    figura.querySelector("figcaption").textContent = archivo.name;
    estado.textContent = "Comprueba que la imagen permita fundamentar la observación registrada.";
  });
  window.addEventListener("pagehide", limpiar);
});
