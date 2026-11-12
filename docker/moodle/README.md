# Siembra automática de Moodle UTA (FISEI)

`seed.php` deja Moodle (`localhost:8080`) con la estructura del aula virtual UTA que usa **EduMonitor AI**.
Es idempotente: crea lo que falta, actualiza lo existente y desmatricula a quien ya no está en la nómina de un curso.

## Cuándo se ejecuta
- **Automáticamente** al arrancar el contenedor `moodle_lms` (`entrypoint-seed.sh` envuelve el entrypoint de Bitnami).
- **Manualmente**, en cualquier momento:
  ```bash
  docker exec moodle_lms bash /opt/edumonitor_seed/entrypoint-seed.sh --seed-only
  ```

## Credenciales
| Rol | Usuario | Contraseña | Notas |
|---|---|---|---|
| Administrador | `admin` | `MoodleAdmin2026!` | Gestión del sitio |
| Docente titular | `hnaranjo` (`docente@uta.edu.ec`) | `Docente2026!` | Profesor con permiso de edición en los 4 cursos. También es el usuario de EduMonitor AI (`localhost:3000`, con el correo) |
| Estudiante | `dcurillo` (caso crítico) | `Estudiante2026!` | Matriculado en los 4 cursos. Los 20 estudiantes comparten contraseña; usuario = inicial + apellido (`candrade`, `mparedes`, …) |

## Cursos y nóminas
| Curso | Shortname | Estudiantes |
|---|---|---|
| (SOF) PROGRAMACION ORIENTADA A OBJETOS - A | `SOF-POO-A` | 7 |
| (SOF) ESTRUCTURA DE DATOS - B | `SOF-ED-B` | 10 |
| (SOF) METODOLOGIAS AGILES - B | `SOF-MA-B` | 12 |
| (SOF) MANEJO Y CONFIGURACION DEL SOFTWARE - A | `SOF-MCS-A` | 15 |

Categorías: `FISEI` → `SOFTWARE` → `Julio a Diciembre 2026`.

## Estructura de cada curso
- **Informativo**: foro de novedades (con aviso de bienvenida), avisos, Sílabo (PDF), Programa Analítico (PDF) y enlace institucional.
- **Primer Parcial** (Unidades 1–2) y **Segundo Parcial** (Unidades 3–4), cada uno con:
  1. *Zona de información*: material PDF y enlace de apoyo por unidad.
  2. *ACD (40%)*: `U1-A1`, `U2-A2` / `U3-A3`, `U4-A4`.
  3. *Aprendizaje Autónomo / Tareas (30%)*: `U1-T1`, `U1-T2`, `U2-T3`, `U2-T4` / `U3-T5` … `U4-T8` (con entrega de archivos).
  4. *PAE (30%)*: `U1-P1`, `U1-P2`, `U2-P3` / `U3-P4` … `U4-P6`.
- **Supletorio**: examen supletorio (`SUP-1`, sin peso en la nota parcial).

## Libro de calificaciones
Media ponderada **ACD 40% / Tareas 30% / PAE 30%**, total sobre 10. Sólo el Primer Parcial está calificado, con notas
distintas en cada curso: aceptables, en riesgo y críticos. Además hay estos casos especiales:
- `dcurillo`: `U1-T2` = 0 y `U2-T4` = 0 con comentario **SIN ENTREGA**.
- El último estudiante de cada nómina tiene `U2-P3` sin nota, con comentario **PENDIENTE DE REVISIÓN**.

## Identidad visual
CSS inyectado en `additionalhtmlhead`: barra superior blanca, barra secundaria del curso en carmesí `#9B1C1C`,
secciones en tarjetas blancas con borde `#DEE2E6` y títulos en azul `#11297A`. La página de inicio es "Mis cursos".

## Web Services
Servicio `EduMonitor_WS` (REST) con token = `MOODLE_TOKEN` del `.env`. El token debe ser alfanumérico
(Moodle quita los demás caracteres del `wstoken`).
