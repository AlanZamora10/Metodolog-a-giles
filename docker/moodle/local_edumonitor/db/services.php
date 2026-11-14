<?php
// This file is part of the EduMonitor AI integration for Moodle UTA (FISEI).

/**
 * Funciones de Web Service del plugin local_edumonitor.
 *
 * @package    local_edumonitor
 * @copyright  2026 Equipo EduMonitor AI - FISEI UTA
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

defined('MOODLE_INTERNAL') || die();

$functions = [
    'local_edumonitor_crear_tarea' => [
        'classname'    => 'local_edumonitor\external\crear_tarea',
        'description'  => 'Crea una tarea de refuerzo en la sección «Refuerzos» del curso, visible sólo para un estudiante.',
        'type'         => 'write',
        'capabilities' => 'moodle/course:manageactivities',
    ],
];
