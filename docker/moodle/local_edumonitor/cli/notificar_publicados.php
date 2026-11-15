<?php
// This file is part of the EduMonitor AI integration for Moodle UTA (FISEI).

/**
 * Notifica (campana de Moodle) a los estudiantes de los refuerzos ya publicados que aún no tienen aviso.
 *
 * Recorre las tareas con idnumber REF-* (creadas por local_edumonitor_crear_tarea), toma el destinatario de
 * la restricción de acceso por correo y envía la notificación una sola vez. No modifica tareas ni notas.
 *
 *   php local/edumonitor/cli/notificar_publicados.php
 *
 * @package    local_edumonitor
 * @copyright  2026 Equipo EduMonitor AI - FISEI UTA
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

define('CLI_SCRIPT', true);

require(__DIR__ . '/../../../config.php');

global $CFG, $DB;

\core\session\manager::set_user(get_admin());

$tareas = $DB->get_records_sql(
    "SELECT cm.id, cm.course, cm.availability
       FROM {course_modules} cm
       JOIN {modules} m ON m.id = cm.module AND m.name = 'assign'
      WHERE cm.idnumber LIKE 'REF-%' AND cm.deletioninprogress = 0
   ORDER BY cm.id");

$enviadas = 0;
foreach ($tareas as $cm) {
    $condiciones = json_decode((string)$cm->availability, true)['c'] ?? [];
    foreach ($condiciones as $c) {
        if (($c['type'] ?? '') !== 'profile' || ($c['sf'] ?? '') !== 'email') {
            continue;
        }
        $estudiante = $DB->get_record('user', ['email' => \core_text::strtolower($c['v']), 'deleted' => 0,
            'mnethostid' => $CFG->mnet_localhost_id]);
        if (!$estudiante) {
            mtrace("  ! cmid {$cm->id}: no existe el usuario {$c['v']}");
            continue;
        }
        [$id, $existente] = \local_edumonitor\notificador::notificar_refuerzo((int)$cm->id, $estudiante);
        mtrace(sprintf("  %s cmid %d -> %s (notificación %d)", $existente ? '=' : '+', $cm->id,
            fullname($estudiante), $id));
        $enviadas += $existente ? 0 : 1;
    }
}
mtrace("Notificaciones nuevas: {$enviadas}");
