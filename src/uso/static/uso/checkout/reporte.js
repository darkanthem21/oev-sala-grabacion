// Evidencias de integridad del reporte de check-out.
document.querySelectorAll(".checkout-pregunta").forEach(pregunta => {
  const evidencia = pregunta.querySelector(".checkout-evidencia");
  if (!evidencia) return;
  function actualizar() {
    const incumple = pregunta.querySelector('input[type="radio"]:checked')?.value === "no";
    evidencia.hidden = !incumple;
    evidencia.querySelectorAll("textarea, input").forEach(campo => {
      campo.required = incumple;
      campo.disabled = !incumple;
      if (campo.tagName === "TEXTAREA") campo.minLength = 10;
    });
  }
  pregunta.querySelectorAll('input[type="radio"]').forEach(radio => radio.addEventListener("change", actualizar));
  actualizar();
});
