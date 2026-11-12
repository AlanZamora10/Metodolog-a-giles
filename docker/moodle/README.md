# Siembra Automatizada e Idempotente para Moodle UTA (FISEI)

Este módulo inicializa el entorno de **Moodle UTA** con la jerarquía institucional, cursos del portafolio, docentes, estudiantes y calificaciones de prueba requeridas para **EduMonitor AI**.

## Componentes Sembrados
1. **Configuración Institucional:**
   - Nombre de sitio: `Moodle UTA`
   - Idioma por defecto: Español (`es`)
2. **Jerarquía de Categorías:**
   - `FISEI` (idnumber `CAT_FISEI`)
     - `SOFTWARE` (idnumber `CAT_SOFTWARE`)
       - `Julio a Diciembre 2026` (idnumber `CAT_2026_JD`)
3. **Usuarios:**
   - Docente: `docente` / `Docente2026!` (`docente@uta.edu.ec`, idnumber `U-01`)
   - 7 Estudiantes: `estudiante_a` hasta `estudiante_g` (idnumbers `U-03` a `U-09`)
4. **4 Cursos del Portafolio (Formato Temas / Topics):**
   - `(SOF) PROGRAMACION ORIENTADA A OBJETOS - A` (`SOF-POO-A`)
   - `(SOF) ESTRUCTURA DE DATOS - B` (`SOF-ED-B`)
   - `(SOF) METODOLOGIAS AGILES - B` (`SOF-MA-B`)
   - `(SOF) MANEJO Y CONFIGURACION DEL SOFTWARE - A` (`SOF-MCS-A`)
5. **Calificaciones y Ponderaciones 40/30/30:**
   - Componente Autónomo (40%)
   - Componente Tareas (30%)
   - Componente PAE (30%)
   - Incluye notas normales, casos críticos (< 5.0), notas `0.0`, estados `SIN_ENTREGA` y `PENDIENTE`.
6. **Web Services REST:**
   - Servicio externo: `EduMonitor_WS`
   - Protocolo: REST activo
   - Token configurado en `.env`: `MOODLE_TOKEN` (`ws_mock_token_uta_fisei_sprint1`)

## Ejecución Manual
Para ejecutar o re-ejecutar la siembra en cualquier momento dentro del contenedor Moodle:
```bash
docker exec moodle_lms php /opt/bitnami/moodle/custom_seed/seed.php
```
