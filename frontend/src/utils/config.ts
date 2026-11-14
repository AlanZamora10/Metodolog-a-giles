/** URL pública de Moodle UTA (enlaces externos: recuperación de contraseña, cursos). */
export const MOODLE_URL = (import.meta.env.VITE_MOODLE_URL || 'http://localhost:8080').replace(/\/+$/, '');

export const URL_RECUPERAR_CLAVE = `${MOODLE_URL}/login/forgot_password.php`;
