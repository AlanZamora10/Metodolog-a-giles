<?php
// This file is part of the EduMonitor AI integration for Moodle UTA (FISEI).

namespace local_edumonitor\external;

defined('MOODLE_INTERNAL') || die();

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_single_structure;
use core_external\external_value;
use local_edumonitor\notificador;

/**
 * local_edumonitor_notificar_refuerzo: notificación oficial (campana de Moodle) al estudiante destinatario
 * de una tarea de refuerzo ya creada con local_edumonitor_crear_tarea. Idempotente por tarea y estudiante.
 *
 * @package    local_edumonitor
 * @copyright  2026 Equipo EduMonitor AI - FISEI UTA
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class notificar_refuerzo extends external_api {

    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'cmid'            => new external_value(PARAM_INT, 'ID del módulo de la tarea de refuerzo'),
            'emailestudiante' => new external_value(PARAM_EMAIL, 'Correo del estudiante destinatario'),
            'indicaciones'    => new external_value(PARAM_RAW, 'Indicaciones del docente (texto plano)', VALUE_DEFAULT, ''),
            'emaildocente'    => new external_value(PARAM_EMAIL, 'Correo del docente remitente', VALUE_DEFAULT, ''),
        ]);
    }

    public static function execute(int $cmid, string $emailestudiante, string $indicaciones = '',
                                   string $emaildocente = ''): array {
        global $CFG, $DB;

        $p = self::validate_parameters(self::execute_parameters(), [
            'cmid' => $cmid, 'emailestudiante' => $emailestudiante, 'indicaciones' => $indicaciones,
            'emaildocente' => $emaildocente,
        ]);
        [$course, $cm] = get_course_and_cm_from_cmid($p['cmid'], 'assign');
        $context = \context_course::instance($course->id);
        self::validate_context($context);
        require_capability('moodle/course:manageactivities', $context);

        $base = ['deleted' => 0, 'mnethostid' => $CFG->mnet_localhost_id];
        $estudiante = $DB->get_record('user', $base + ['email' => \core_text::strtolower($p['emailestudiante'])]);
        if (!$estudiante || !is_enrolled($context, $estudiante, '', true)) {
            throw new \invalid_parameter_exception('El estudiante no está matriculado (activo) en el curso.');
        }
        $docente = $p['emaildocente']
            ? ($DB->get_record('user', $base + ['email' => \core_text::strtolower($p['emaildocente'])]) ?: null)
            : null;

        [$id, $existente] = notificador::notificar_refuerzo($cm->id, $estudiante, $p['indicaciones'], $docente);
        return ['notificacionid' => $id, 'existente' => $existente];
    }

    public static function execute_returns(): external_single_structure {
        return new external_single_structure([
            'notificacionid' => new external_value(PARAM_INT, 'ID de la notificación en {notifications}'),
            'existente'      => new external_value(PARAM_BOOL, 'true si el estudiante ya tenía esa notificación'),
        ]);
    }
}
