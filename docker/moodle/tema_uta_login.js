/*
 * Moodle UTA · acceso institucional con el flujo «Microsoft Office 365» de la Plataforma Educativa UTA.
 *
 * Mejora progresiva de login/index.php: muestra primero la tarjeta con el botón «Microsoft Office 365» y,
 * al pulsarlo, despliega (sin recargar) el formulario nativo de Moodle con una opción para volver.
 * No cambia el formulario: #login, #username, #password y #loginbtn siguen siendo los de Moodle, y sin
 * JavaScript la página se ve como siempre. Si Moodle devuelve un error de acceso, el formulario se abre
 * directamente para mostrarlo.
 */
(function () {
  'use strict';

  var ICONO = '<svg width="20" height="20" viewBox="0 0 21 21" aria-hidden="true" focusable="false">' +
    '<rect x="1" y="1" width="9" height="9" fill="#F25022"/><rect x="11" y="1" width="9" height="9" fill="#7FBA00"/>' +
    '<rect x="1" y="11" width="9" height="9" fill="#00A4EF"/><rect x="11" y="11" width="9" height="9" fill="#FFB900"/></svg>';

  function iniciar() {
    if (!document.body || document.body.id !== 'page-login-index') {
      return;
    }
    var bloque = document.querySelector('.login-container .loginform');
    var formulario = document.getElementById('login');
    if (!bloque || !formulario || bloque.querySelector('.uta-portada')) {
      return;
    }
    var tarjeta = bloque.closest('.login-container');

    var portada = document.createElement('div');
    portada.className = 'uta-portada';
    portada.innerHTML = '<p class="uta-portada-sub">Identifíquese usando su cuenta en:</p>' +
      '<button type="button" class="uta-o365-btn" aria-controls="login" aria-expanded="false">' +
      ICONO + '<span>Microsoft Office 365</span></button>';
    bloque.insertBefore(portada, bloque.firstChild);
    var boton = portada.querySelector('button');

    var volver = document.createElement('button');
    volver.type = 'button';
    volver.className = 'uta-volver';
    volver.textContent = '← Volver a las opciones de acceso';
    formulario.appendChild(volver);

    function abrir(enfocar) {
      tarjeta.classList.remove('uta-paso-inicio');
      tarjeta.classList.add('uta-paso-credenciales');
      boton.setAttribute('aria-expanded', 'true');
      if (enfocar) {
        var usuario = document.getElementById('username');
        if (usuario) {
          usuario.focus();
        }
      }
    }

    function cerrar() {
      tarjeta.classList.remove('uta-paso-credenciales');
      tarjeta.classList.add('uta-paso-inicio');
      boton.setAttribute('aria-expanded', 'false');
      boton.focus();
    }

    boton.addEventListener('click', function () { abrir(true); });
    volver.addEventListener('click', cerrar);

    var hayError = document.querySelector('#loginerrormessage, .loginerrors, .login-container .alert-danger');
    if (hayError) {
      abrir(false);
    } else {
      tarjeta.classList.add('uta-paso-inicio');
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', iniciar);
  } else {
    iniciar();
  }
})();
