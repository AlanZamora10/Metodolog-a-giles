<?php
// This file is part of the EduMonitor AI integration for Moodle UTA (FISEI).

/**
 * Plugin local de EduMonitor AI: Web Service para publicar tareas de refuerzo personalizadas.
 *
 * @package    local_edumonitor
 * @copyright  2026 Equipo EduMonitor AI - FISEI UTA
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

defined('MOODLE_INTERNAL') || die();

$plugin->component = 'local_edumonitor';
$plugin->version   = 2026111400;
$plugin->requires  = 2023100900; // Moodle 4.3.
$plugin->maturity  = MATURITY_STABLE;
$plugin->release   = '1.0.0';
