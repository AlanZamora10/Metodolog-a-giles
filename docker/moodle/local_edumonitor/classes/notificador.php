<?php
// This file is part of the EduMonitor AI integration for Moodle UTA (FISEI).

namespace local_edumonitor;

defined('MOODLE_INTERNAL') || die();

global $CFG;
require_once($CFG->libdir . '/messagelib.php');

/**
 * Notificación oficial de Moodle (campana superior) para una actividad de refuerzo.
 *
 * Usa la API de mensajería (message_send) con el proveedor local_edumonitor/refuerzo_asignado, que
 * registra la notificación no leída en {notifications} y {message_popup_notifications}.
 * Es idempotente: si el estudiante ya tiene la notificación de esa tarea, devuelve la existente.
 *
 * @package    local_edumonitor
 * @copyright  2026 Equipo EduMonitor AI - FISEI UTA
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class notificador {

    /** Nombre del proveedor de mensajes (db/messages.php). */
    const PROVEEDOR = 'refuerzo_asignado';

    /**
     * Envía (una sola vez) la notificación del refuerzo al estudiante.
     *
     * @param int $cmid Módulo de la tarea de refuerzo (assign)
     * @param \stdClass $estudiante Destinatario (useridto)
     * @param string $indicaciones Indicaciones del docente (texto plano); vacío = descripción de la tarea
     * @param \stdClass|null $docente Remitente; null = docente titular del curso o usuario «no responder»
     * @return array [id de la notificación, true si ya existía]
     */
    public static function notificar_refuerzo(int $cmid, \stdClass $estudiante, string $indicaciones = '',
                                              ?\stdClass $docente = null): array {
        global $DB;

        [$course, $cm] = get_course_and_cm_from_cmid($cmid, 'assign');
        // Enlace relativo a la raíz del sitio: Moodle arma su wwwroot con el header Host (127.0.0.1 en CLI,
        // el host interno de Docker en las llamadas del middleware), así que una URL absoluta no serviría en el
        // navegador. La campana lo resuelve contra el host real (mark_notification_read.php -> redirect).
        $url = (new \moodle_url('/mod/assign/view.php', ['id' => $cm->id]))->out_as_local_url(false);

        $existente = $DB->get_field_select('notifications', 'id',
            'useridto = :u AND component = :c AND eventtype = :e AND ' . $DB->sql_like('contexturl', ':url'),
            ['u' => $estudiante->id, 'c' => 'local_edumonitor', 'e' => self::PROVEEDOR, 'url' => '%' . $url],
            IGNORE_MULTIPLE);
        if ($existente) {
            return [(int)$existente, true];
        }

        $tarea = $DB->get_record('assign', ['id' => $cm->instance], 'name, intro, duedate', MUST_EXIST);
        $curso = format_string($course->fullname, true, ['context' => \context_course::instance($course->id)]);
        $titulo = format_string($tarea->name);
        $indicaciones = trim($indicaciones) !== '' ? trim($indicaciones)
            : trim(html_to_text($tarea->intro, 0, false));
        $docente = $docente ?: self::docente_titular($course->id) ?: \core_user::get_noreply_user();
        $entrega = $tarea->duedate ? userdate($tarea->duedate, get_string('strftimedatetime', 'langconfig')) : '';

        $asunto = "Nueva actividad de refuerzo asignada — {$curso}";
        $texto = "Su docente " . fullname($docente) . " le asignó una actividad de refuerzo personalizada.\n\n"
            . "Actividad: {$titulo}\n"
            . "Curso: {$curso}\n"
            . ($entrega ? "Fecha de entrega: {$entrega}\n" : '')
            . "\nIndicaciones del docente:\n{$indicaciones}\n\n"
            . "Abrir la tarea en Moodle UTA: {$url}";
        $html = '<p>Su docente <strong>' . s(fullname($docente)) . '</strong> le asignó una actividad de refuerzo '
            . 'personalizada.</p>'
            . '<p><strong>Actividad:</strong> ' . s($titulo) . '<br><strong>Curso:</strong> ' . s($curso)
            . ($entrega ? '<br><strong>Fecha de entrega:</strong> ' . s($entrega) : '') . '</p>'
            . '<p><strong>Indicaciones del docente:</strong></p><p>' . nl2br(s($indicaciones)) . '</p>'
            . '<p><a href="' . s($url) . '">Abrir la tarea en Moodle</a></p>';

        $mensaje = new \core\message\message();
        $mensaje->component = 'local_edumonitor';
        $mensaje->name = self::PROVEEDOR;
        $mensaje->userfrom = $docente;
        $mensaje->userto = $estudiante;
        $mensaje->subject = $asunto;
        $mensaje->fullmessage = $texto;
        $mensaje->fullmessageformat = FORMAT_PLAIN;
        $mensaje->fullmessagehtml = $html;
        $mensaje->smallmessage = "{$titulo} — {$curso}";
        $mensaje->notification = 1;
        $mensaje->contexturl = $url;
        $mensaje->contexturlname = $titulo;
        $mensaje->courseid = $course->id;

        $id = message_send($mensaje);
        if (!$id) {
            throw new \moodle_exception('errornotificacion', 'local_edumonitor');
        }
        return [(int)$id, false];
    }

    /** Primer docente con permiso de edición del curso (remitente de la notificación). */
    private static function docente_titular(int $courseid): ?\stdClass {
        $docentes = get_enrolled_users(\context_course::instance($courseid), 'moodle/course:manageactivities', 0,
            'u.*', 'u.id ASC', 0, 1, true);
        return $docentes ? reset($docentes) : null;
    }
}
