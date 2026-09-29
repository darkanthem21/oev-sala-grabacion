const MIN_OBSERVATION_LENGTH = 10;

const steps = [
  {
    label: 'Sección 1: Estado e Integridad',
    title: 'Integridad de la sala',
    group: 'Integridad de la Sala',
    questions: [
      'Paredes y paneles acústicos sin daños',
      'Puerta y sellos acústicos funcionando',
    ],
  },
  {
    label: 'Sección 2: Orden y Limpieza',
    title: 'Orden y limpieza',
    group: 'Orden y Limpieza',
    questions: [
      'Sala despejada de basura y objetos personales',
      'Mobiliario (sillas, mesas) en su posición original',
    ],
  },
  {
    label: 'Sección 3: Equipamiento Técnico',
    title: 'Equipos y cables',
    group: 'Equipos y Cables',
    questions: [
      'Micrófonos y cables enrollados correctamente',
      'Consola y periféricos apagados/protegidos',
      '¿Algún equipo o cable presenta daños?',
    ],
  },
  {
    label: 'Sección 4: Cumplimiento y Cierre',
    title: 'Cumplimiento de horario y entrega',
    group: 'Cumplimiento de Horario',
    questions: [
      '¿El ingreso fue a la hora prevista?',
      '¿La desocupación fue a la hora prevista?',
    ],
    requiresClosingFields: true,
  },
];

let currentStep = 0;
let finalPhotoUrl = '';

const answers = {};
const integrityPhotos = {};
const $ = (selector) => document.querySelector(selector);

function answerKey(questionIndex) {
  return `${currentStep}-${questionIndex}`;
}

function observationKey(questionIndex) {
  return `obs-${currentStep}-${questionIndex}`;
}

function integrityPhotoKey(questionIndex) {
  return `foto-integridad-${currentStep}-${questionIndex}`;
}

function checked(value, expected) {
  return value === expected ? 'checked' : '';
}

function selectedNoFields(questionIndex) {
  const obsKey = observationKey(questionIndex);
  const photoKey = integrityPhotoKey(questionIndex);
  const observation = answers[obsKey] || '';
  const photoUrl = integrityPhotos[photoKey] || '';
  const photoState = photoUrl ? '' : 'hidden';

  return `<div class="observacion-no">
    <label class="label" for="${obsKey}">Observación</label>
    <textarea id="${obsKey}" data-observation="${questionIndex}" placeholder="Describe el motivo del No.">${observation}</textarea>
    <small class="requisito">Mínimo ${MIN_OBSERVATION_LENGTH} caracteres.</small>

    <div class="foto-integridad">
      <span class="label">Foto de integridad</span>
      <label class="subida">Tomar o adjuntar fotografía de respaldo
        <small>Obligatoria cuando la respuesta es No.</small>
        <input type="file" id="${photoKey}" data-integrity-photo="${questionIndex}" accept="image/*" capture="environment">
      </label>
      <img id="preview-${photoKey}" class="preview ${photoState}" src="${photoUrl}" alt="Vista previa de la fotografía de integridad">
      <button type="button" class="btn anterior ${photoState}" data-remove-integrity-photo="${questionIndex}">Quitar foto</button>
    </div>
  </div>`;
}

function questionHtml(question, questionIndex) {
  const key = answerKey(questionIndex);
  const value = answers[key] || '';
  const noFields = value === 'no' ? selectedNoFields(questionIndex) : '';
  const noClass = value === 'no' ? ' no' : '';

  return `<div class="pregunta${noClass}">
    <span>${question}</span>
    <div class="opciones">
      <label><input type="radio" name="${key}" value="si" ${checked(value, 'si')}>Sí</label>
      <label><input type="radio" name="${key}" value="no" ${checked(value, 'no')}>No</label>
    </div>
    ${noFields}
  </div>`;
}

function closingFieldsHtml() {
  const photoState = finalPhotoUrl ? '' : 'hidden';

  return `<div class="campo">
    <label class="label" for="arrive">Hora efectiva de salida</label>
    <input id="arrive" type="time" value="${answers.arrive || ''}">
  </div>
  <div class="campo">
    <label class="label" for="closeobs">Observaciones finales (opcional)</label>
    <textarea id="closeobs" placeholder="Detalles adicionales...">${answers.closeobs || ''}</textarea>
  </div>
  <div class="campo">
    <span class="label">Foto de fidelidad / entrega</span>
    <label class="subida">Tomar o adjuntar fotografía final
      <small>Captura el estado general de la sala al finalizar la inspección.</small>
      <input type="file" id="finalPhoto" accept="image/*" capture="environment">
    </label>
    <img id="finalPreview" class="preview ${photoState}" src="${finalPhotoUrl}" alt="Vista previa de la fotografía final">
    <button type="button" id="removeFinalPhoto" class="btn anterior ${photoState}">Quitar foto</button>
  </div>`;
}

function stepContentHtml(step) {
  const questions = step.questions
    .map((question, questionIndex) => questionHtml(question, questionIndex))
    .join('');
  const closingFields = step.requiresClosingFields ? closingFieldsHtml() : '';

  return `<h3>${step.group}</h3>${questions}${closingFields}`;
}

function updateProgress(step) {
  const percent = Math.round(((currentStep + 1) / steps.length) * 100);

  $('#stepCounter').textContent = `Paso ${currentStep + 1} de ${steps.length}`;
  $('#percent').textContent = `${percent}% completado`;
  $('#progress').style.width = `${percent}%`;
  $('#sectionLabel').textContent = step.label;
  $('#sectionTitle').textContent = step.title;
}

function render() {
  const step = steps[currentStep];

  updateProgress(step);
  $('#back').disabled = currentStep === 0;
  $('#forward').classList.toggle('hidden', currentStep === steps.length - 1);
  $('#submit').classList.toggle('hidden', currentStep !== steps.length - 1);
  $('#error').textContent = '';
  $('#stepContent').innerHTML = stepContentHtml(step);

  bindStepEvents();
}

function clearIntegrityPhoto(questionIndex) {
  const key = integrityPhotoKey(questionIndex);
  if (integrityPhotos[key]) URL.revokeObjectURL(integrityPhotos[key]);
  delete integrityPhotos[key];
}

function handleAnswerChange(event, questionIndex) {
  answers[answerKey(questionIndex)] = event.target.value;
  if (event.target.value === 'si') {
    delete answers[observationKey(questionIndex)];
    clearIntegrityPhoto(questionIndex);
  }
  render();
}

function bindQuestionEvents(step) {
  step.questions.forEach((_, questionIndex) => {
    document.querySelectorAll(`input[name="${answerKey(questionIndex)}"]`).forEach((element) => {
      element.addEventListener('change', (event) => handleAnswerChange(event, questionIndex));
    });
  });
}

function bindObservationEvents() {
  document.querySelectorAll('[data-observation]').forEach((element) => {
    element.addEventListener('input', () => {
      answers[observationKey(element.dataset.observation)] = element.value;
    });
  });
}

function bindIntegrityPhotoEvents() {
  document.querySelectorAll('[data-integrity-photo]').forEach((element) => {
    element.addEventListener('change', () => {
      const selected = element.files[0];
      if (!selected) return;

      const key = integrityPhotoKey(element.dataset.integrityPhoto);
      if (integrityPhotos[key]) URL.revokeObjectURL(integrityPhotos[key]);
      integrityPhotos[key] = URL.createObjectURL(selected);
      render();
    });
  });

  document.querySelectorAll('[data-remove-integrity-photo]').forEach((element) => {
    element.addEventListener('click', () => {
      clearIntegrityPhoto(element.dataset.removeIntegrityPhoto);
      render();
    });
  });
}

function bindClosingFieldEvents() {
  const closeObservation = $('#closeobs');
  if (closeObservation) {
    closeObservation.addEventListener('input', () => {
      answers.closeobs = closeObservation.value;
    });
  }

  const departureTime = $('#arrive');
  if (departureTime) {
    departureTime.addEventListener('input', () => {
      answers.arrive = departureTime.value;
    });
  }
}

function bindFinalPhotoEvents() {
  const finalPhoto = $('#finalPhoto');
  if (finalPhoto) {
    finalPhoto.addEventListener('change', () => {
      const selected = finalPhoto.files[0];
      if (!selected) return;

      if (finalPhotoUrl) URL.revokeObjectURL(finalPhotoUrl);
      finalPhotoUrl = URL.createObjectURL(selected);
      $('#finalPreview').src = finalPhotoUrl;
      $('#finalPreview').classList.remove('hidden');
      $('#removeFinalPhoto').classList.remove('hidden');
    });
  }

  const removeFinalPhoto = $('#removeFinalPhoto');
  if (removeFinalPhoto) {
    removeFinalPhoto.addEventListener('click', () => {
      finalPhotoUrl = '';
      $('#finalPreview').classList.add('hidden');
      removeFinalPhoto.classList.add('hidden');
      $('#finalPhoto').value = '';
    });
  }
}

function bindStepEvents() {
  const step = steps[currentStep];

  bindQuestionEvents(step);
  bindObservationEvents();
  bindIntegrityPhotoEvents();
  bindClosingFieldEvents();
  bindFinalPhotoEvents();
}

function validateStep() {
  const step = steps[currentStep];

  for (let questionIndex = 0; questionIndex < step.questions.length; questionIndex += 1) {
    const answer = answers[answerKey(questionIndex)];
    const observationLength = answers[observationKey(questionIndex)]?.trim().length || 0;

    if (!answer) return 'Responde todas las preguntas antes de continuar.';
    if (answer === 'no' && observationLength < MIN_OBSERVATION_LENGTH) {
      return `Agrega una observación de al menos ${MIN_OBSERVATION_LENGTH} caracteres para cada respuesta No.`;
    }
    if (answer === 'no' && !integrityPhotos[integrityPhotoKey(questionIndex)]) {
      return 'Adjunta una foto de integridad para cada respuesta marcada como No.';
    }
  }

  if (step.requiresClosingFields && !answers.arrive) return 'Indica la hora efectiva de salida.';
  return '';
}

function showError(message) {
  $('#error').textContent = message;
}

function nextStep() {
  const error = validateStep();
  if (error) {
    showError(error);
    return;
  }

  currentStep += 1;
  render();
}

function previousStep() {
  if (currentStep === 0) return;
  currentStep -= 1;
  render();
}

function reportData() {
  return {
    reserva: 'Sala Virtual',
    horario: '09:00-12:00',
    horaSalida: answers.arrive,
    finalizado: new Date().toLocaleString('es-CL'),
    respuestas: answers,
    fotografiasIntegridad: Object.keys(integrityPhotos),
    fotografiaAdjunta: Boolean(finalPhotoUrl),
  };
}

function finishReport() {
  const error = validateStep();
  if (error) {
    showError(error);
    return;
  }

  const report = reportData();
  localStorage.setItem('reporteCierreSala', JSON.stringify(report));

  $('#formView').classList.add('hidden');
  $('#doneView').classList.remove('hidden');
  $('#summary').innerHTML = `<h3>Resumen del cierre</h3>
    <p><b>Sala:</b> Sala Virtual</p>
    <p><b>Hora de salida:</b> ${answers.arrive}</p>
    <p><b>Fotos de integridad:</b> ${Object.keys(integrityPhotos).length}</p>
    <p><b>Fotografía final:</b> ${finalPhotoUrl ? 'Adjunta' : 'No adjunta'}</p>
    <p><b>Registro:</b> ${report.finalizado}</p>`;
}

$('#back').addEventListener('click', previousStep);
$('#forward').addEventListener('click', nextStep);
$('#submit').addEventListener('click', finishReport);

render();
