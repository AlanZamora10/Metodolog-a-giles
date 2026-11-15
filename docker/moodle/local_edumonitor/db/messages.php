<?php
// This file is part of the EduMonitor AI integration for Moodle UTA (FISEI).

/**
 * Proveedores de mensajes de local_edumonitor.
 *
 * refuerzo_asignado: aviso al estudiante (campana de notificaciones) cuando su docente le publica
 * una actividad de refuerzo personalizada desde EduMonitor AI.
 *
 * @package    local_edumonitor
 * @copyright  2026 Equipo EduMonitor AI - FISEI UTA
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

defined('MOODLE_INTERNAL') || die();

$messageproviders = [
    'refuerzo_asignado' => [
        'capability' => 'mod/assign:view',
        'defaults' => [
            'popup' => MESSAGE_PERMITTED + MESSAGE_DEFAULT_ENABLED,
            'email' => MESSAGE_PERMITTED,
        ],
    ],
];
