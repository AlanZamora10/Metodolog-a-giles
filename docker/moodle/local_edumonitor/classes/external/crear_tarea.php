<?php
// This file is part of the EduMonitor AI integration for Moodle UTA (FISEI).

namespace local_edumonitor\external;

defined('MOODLE_INTERNAL') || die();

global $CFG;
require_once($CFG->dirroot . '/course/lib.php');
require_once($CFG->dirroot . '/course/modlib.php');
require_once($CFG->dirroot . '/mod/assign/lib.php');

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_single_structure;
use core_external\external_value;

/**
 * local_edumonitor_crear_tarea: crea una tarea de refuerzo visible sólo para un estudiante.
 *
 * - La tarea se crea en la sección «Refuerzos» del curso (se crea si no existe).
 * - La visibilidad se restringe con la condición de acceso por perfil (correo del estudiante),
 *   de modo que el resto de la clase no la ve (showc = false).
 * - Es idempotente por `codigo` (idnumber del módulo): si ya existe, devuelve la existente.
 *
 * @package    local_edumonitor
 * @copyright  2026 Equipo EduMonitor AI - FISEI UTA
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class crear_tarea extends external_api {

    /** Nombre de la sección donde se publican los refuerzos. */
    const SECCION = 'Refuerzos';

    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'courseid'        => new external_value(PARAM_INT, 'ID del curso'),
            'nombre'          => new external_value(PARAM_TEXT, 'Nombre de la tarea'),
            'instrucciones'   => new external_value(PARAM_RAW, 'Instrucciones para el estudiante (texto plano)'),
            'emailestudiante' => new external_value(PARAM_EMAIL, 'Correo del estudiante destinatario'),
            'fechaentrega'    => new external_value(PARAM_INT, 'Fecha límite (marca de tiempo Unix)'),
            'codigo'          => new external_value(PARAM_ALPHANUMEXT, 'Código único de la tarea (idnumber)'),
        ]);
    }

    public static function execute(int $courseid, string $nombre, string $instrucciones, string $emailestudiante,
                                   int $fechaentrega, string $codigo): array {
        global $CFG, $DB;

        $p = self::validate_parameters(self::execute_parameters(), [
            'courseid' => $courseid, 'nombre' => $nombre, 'instrucciones' => $instrucciones,
            'emailestudiante' => $emailestudiante, 'fechaentrega' => $fechaentrega, 'codigo' => $codigo,
        ]);

        $course = get_course($p['courseid']);
        $context = \context_course::instance($course->id);
        self::validate_context($context);
        require_capability('moodle/course:manageactivities', $context);

        $estudiante = $DB->get_record('user', [
            'email' => \core_text::strtolower($p['emailestudiante']), 'deleted' => 0, 'mnethostid' => $CFG->mnet_localhost_id,
        ]);
        if (!$estudiante || !is_enrolled($context, $estudiante, '', true)) {
            throw new \invalid_parameter_exception('El estudiante no está matriculado (activo) en el curso.');
        }
        if ($p['fechaentrega'] <= time()) {
            throw new \invalid_parameter_exception('La fecha de entrega debe ser futura.');
        }

        // Idempotencia: el mismo código no crea una segunda tarea
        $existente = $DB->get_record('course_modules', ['course' => $course->id, 'idnumber' => $p['codigo']]);
        if ($existente) {
            $seccion = $DB->get_field('course_sections', 'section', ['id' => $existente->section]);
            return self::respuesta((int)$existente->id, (int)$seccion, true);
        }

        $seccion = self::seccion_refuerzos($course);
        $moduleinfo = (object)[
            'modulename' => 'assign',
            'module' => $DB->get_field('modules', 'id', ['name' => 'assign'], MUST_EXIST),
            'course' => $course->id,
            'section' => $seccion,
            'visible' => 1,
            'visibleoncoursepage' => 1,
            'cmidnumber' => $p['codigo'],
            'name' => $p['nombre'],
            'introeditor' => [
                'text' => '<p>' . nl2br(s($p['instrucciones'])) . '</p>',
                'format' => FORMAT_HTML,
                'itemid' => file_get_unused_draft_itemid(),
            ],
            'showdescription' => 0,
            'alwaysshowdescription' => 1,
            'nosubmissions' => 0,
            'submissiondrafts' => 0,
            'requiresubmissionstatement' => 0,
            'sendnotifications' => 0,
            'sendlatenotifications' => 0,
            'sendstudentnotifications' => 1,
            'allowsubmissionsfromdate' => time(),
            'duedate' => $p['fechaentrega'],
            'cutoffdate' => 0,
            'gradingduedate' => $p['fechaentrega'] + 7 * DAYSECS,
            'grade' => 10,
            'gradepass' => 0,
            'completion' => 0,
            'completionsubmit' => 0,
            'teamsubmission' => 0,
            'requireallteammemberssubmit' => 0,
            'teamsubmissiongroupingid' => 0,
            'blindmarking' => 0,
            'hidegrader' => 0,
            'attemptreopenmethod' => 'untilpass',
            'maxattempts' => -1,
            'markingworkflow' => 0,
            'markingallocation' => 0,
            'preventsubmissionnotingroup' => 0,
            'groupmode' => 0,
            'groupingid' => 0,
            'assignsubmission_onlinetext_enabled' => 1,
            'assignsubmission_file_enabled' => 1,
            'assignsubmission_file_maxfiles' => 5,
            'assignsubmission_file_maxsizebytes' => 10485760,
            'assignsubmission_file_filetypes' => '',
            'assignfeedback_comments_enabled' => 1,
            // Sólo el estudiante destinatario ve la tarea (condición de perfil por correo, oculta al resto)
            'availability' => json_encode([
                'op' => '&',
                'c' => [['type' => 'profile', 'sf' => 'email', 'op' => 'isequalto', 'v' => $estudiante->email]],
                'showc' => [false],
            ]),
        ];
        $moduleinfo = add_moduleinfo($moduleinfo, $course);

        // El refuerzo se califica, pero no pondera en la nota del parcial (peso 0 en la media ponderada)
        require_once($CFG->libdir . '/gradelib.php');
        $item = \grade_item::fetch(['courseid' => $course->id, 'itemtype' => 'mod', 'itemmodule' => 'assign',
                                    'iteminstance' => $moduleinfo->instance]);
        if ($item && (float)$item->aggregationcoef !== 0.0) {
            $item->aggregationcoef = 0;
            $item->update('local_edumonitor');
        }
        return self::respuesta((int)$moduleinfo->coursemodule, $seccion, false);
    }

    /** Número de la sección «Refuerzos» del curso; la crea al final si no existe. */
    private static function seccion_refuerzos(\stdClass $course): int {
        global $DB;
        $existente = $DB->get_record('course_sections', ['course' => $course->id, 'name' => self::SECCION]);
        if ($existente) {
            return (int)$existente->section;
        }
        $nueva = course_create_section($course, 0);
        course_update_section($course, $nueva, [
            'name' => self::SECCION,
            'summary' => '<p>Tareas de refuerzo personalizadas generadas desde EduMonitor AI.</p>',
            'summaryformat' => FORMAT_HTML,
        ]);
        return (int)$nueva->section;
    }

    private static function respuesta(int $cmid, int $seccion, bool $existente): array {
        $url = new \moodle_url('/mod/assign/view.php', ['id' => $cmid]);
        return ['cmid' => $cmid, 'url' => $url->out(false), 'seccion' => $seccion, 'existente' => $existente];
    }

    public static function execute_returns(): external_single_structure {
        return new external_single_structure([
            'cmid'      => new external_value(PARAM_INT, 'ID del módulo (tarea) creado en Moodle'),
            'url'       => new external_value(PARAM_URL, 'Enlace a la tarea'),
            'seccion'   => new external_value(PARAM_INT, 'Número de la sección «Refuerzos»'),
            'existente' => new external_value(PARAM_BOOL, 'true si la tarea ya existía con ese código'),
        ]);
    }
}
