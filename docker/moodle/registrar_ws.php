<?php
/**
 * Agrega las funciones del plugin local_edumonitor al servicio EduMonitor_WS (si el servicio ya existe).
 * No toca usuarios, cursos ni calificaciones. Lo usa `entrypoint-seed.sh --plugin-only`.
 */

define('CLI_SCRIPT', true);
require('/opt/bitnami/moodle/config.php');

global $DB;

$service = $DB->get_record('external_services', ['name' => 'EduMonitor_WS']);
if (!$service) {
    echo "[EduMonitor AI] El servicio EduMonitor_WS aún no existe (lo crea seed.php).\n";
    exit(0);
}
foreach (['local_edumonitor_crear_tarea', 'local_edumonitor_publicar_refuerzo', 'local_edumonitor_notificar_refuerzo',
          'core_course_get_contents']
         as $fn) {
    if ($DB->record_exists('external_functions', ['name' => $fn]) &&
        !$DB->record_exists('external_services_functions', ['externalserviceid' => $service->id, 'functionname' => $fn])) {
        $DB->insert_record('external_services_functions', (object)['externalserviceid' => $service->id, 'functionname' => $fn]);
        echo "[EduMonitor AI] + $fn agregado a EduMonitor_WS\n";
    }
}
echo "[EduMonitor AI] Funciones del plugin registradas en EduMonitor_WS.\n";
