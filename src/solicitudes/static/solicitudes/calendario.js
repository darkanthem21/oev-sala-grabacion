document.addEventListener("DOMContentLoaded", function() {
    const celdasSeleccionables = document.querySelectorAll('.calendario td.dia-seleccionable');
    const panelBloques = document.getElementById('panel-bloques');
    const btnConfirmar = document.getElementById('btn-confirmar');
    const bloquesUrl = (panelBloques && panelBloques.dataset.bloquesUrl) ? panelBloques.dataset.bloquesUrl : '/solicitar/bloques/';

    // Manejo de clic en los días del calendario
    celdasSeleccionables.forEach(celda => {
        celda.addEventListener('click', function() {
            const fecha = this.getAttribute('data-date');
            if (!fecha) return;

            // Actualizar selección visual del día
            celdasSeleccionables.forEach(c => c.classList.remove('selected'));
            this.classList.add('selected');

            // Indicador de carga
            panelBloques.innerHTML = '<div class="cargando-bloques"><p>Buscando bloques para ' + fecha + '...</p></div>';

            // Consultar los bloques a través de la aplicación solicitudes
            fetch(`${bloquesUrl}?fecha=${encodeURIComponent(fecha)}`)
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Error al consultar bloques');
                    }
                    return response.text();
                })
                .then(html => {
                    panelBloques.innerHTML = html;
                })
                .catch(error => {
                    console.error('Error:', error);
                    panelBloques.innerHTML = '<div class="sin-bloques"><p>Error al cargar los bloques del día seleccionado.</p></div>';
                });
        });
    });

    if (panelBloques) {
        // Delegación de eventos para la selección múltiple de bloques disponibles
        panelBloques.addEventListener('click', function(e) {
            const tarjeta = e.target.closest('.tarjeta-bloque.disponible');
            if (!tarjeta) return;

            const isSelected = tarjeta.classList.toggle('selected');
            tarjeta.setAttribute('aria-pressed', isSelected ? 'true' : 'false');
        });

        // Accesibilidad por teclado (Enter o Espacio)
        panelBloques.addEventListener('keydown', function(e) {
            if (e.key === ' ' || e.key === 'Enter') {
                const tarjeta = e.target.closest('.tarjeta-bloque.disponible');
                if (tarjeta && document.activeElement === tarjeta) {
                    e.preventDefault();
                    tarjeta.click();
                }
            }
        });
    }

    // Botón de confirmación de selección
    if (btnConfirmar) {
        btnConfirmar.addEventListener('click', function() {
            const celdaSeleccionada = document.querySelector('.calendario td.dia-seleccionable.selected');

            if (!celdaSeleccionada) {
                alert("Por favor, selecciona un día del calendario.");
                return;
            }

            const fecha = celdaSeleccionada.getAttribute('data-date');
            const bloquesSeleccionados = Array.from(document.querySelectorAll('.tarjeta-bloque.disponible.selected'))
                .map(t => t.getAttribute('data-hora'));

            if (bloquesSeleccionados.length === 0) {
                alert("Día seleccionado: " + fecha + "\nPor favor, selecciona al menos un bloque disponible.");
                return;
            }

            alert("Día seleccionado: " + fecha + "\nBloque(s) seleccionado(s):\n• " + bloquesSeleccionados.join("\n• "));
        });
    }
});
