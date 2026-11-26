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
Contraseña de **todos** los docentes y estudiantes: `PrimerNombrePrimerApellido1!` (primera letra en mayúscula, sin
tildes ni espacios). Correo institucional = inicial del primer nombre + primer apellido + 4 últimos dígitos de la cédula
(campo de perfil «Cédula»); se ingresa con el correo completo.

| Rol | Usuario | Contraseña | Notas |
|---|---|---|---|
| Administrador | `admin` | `MoodleAdmin2026!` | Gestión del sitio |
| Docente | `rgomez4824@uta.edu.ec` (Ing. Roberto Patricio Gómez Salazar, C.I. 1803454824) | `RobertoGomez1!` | Titular de POO, ED, MA y MCS. Mismo correo para EduMonitor AI (`localhost:3000`) |
| Docente | `pvillacis7138@uta.edu.ec` (Ing. Patricia Elena Villacís Paredes, C.I. 1802657138) | `PatriciaVillacis1!` | Titular de IS1, BDA y DW. Mismo correo para EduMonitor AI |
| Estudiante | `cmendoza3199@uta.edu.ec` (Carlos Andrés Mendoza Paredes, caso crítico) | `CarlosMendoza1!` | Matriculado en los 4 cursos de Roberto Gómez |
| Estudiante | `dherrera9463@uta.edu.ec` (Diana Carolina Herrera Medina) | `DianaHerrera1!` | Cursa IS1 y DW con Patricia Villacís |

Cada docente sólo ve en EduMonitor AI sus propios cursos, estudiantes, métricas y alertas.

## Cursos y nóminas
| Curso | Shortname | Docente | Estudiantes |
|---|---|---|---|
| (SOF) PROGRAMACION ORIENTADA A OBJETOS - A | `SOF-POO-A` | Roberto Gómez | 7 |
| (SOF) ESTRUCTURA DE DATOS - B | `SOF-ED-B` | Roberto Gómez | 10 |
| (SOF) METODOLOGIAS AGILES - B | `SOF-MA-B` | Roberto Gómez | 12 |
| (SOF) MANEJO Y CONFIGURACION DEL SOFTWARE - A | `SOF-MCS-A` | Roberto Gómez | 15 |
| (SOF) INGENIERIA DE SOFTWARE I - A | `SOF-IS1-A` | Patricia Villacís | 8 |
| (SOF) BASES DE DATOS AVANZADAS - B | `SOF-BDA-B` | Patricia Villacís | 7 |
| (SOF) DESARROLLO WEB - A | `SOF-DW-A` | Patricia Villacís | 9 |

Siembra parcial (sólo algunos cursos; no toca aulas, fechas ni notas de los demás, pero sí usuarios y contraseñas):
```bash
docker exec moodle_lms php /opt/edumonitor_seed/seed.php --cursos=SOF-IS1-A,SOF-BDA-B,SOF-DW-A
```

Categorías: `FISEI` → `SOFTWARE` → `Julio a Diciembre 2026`.

### Curso Cálculo (Telecomunicaciones)
`seed_calculo.php` crea `SOF-CAL-A` «(TEL) CALCULO - A» (docente `rgomez`) en `FISEI` → `TELECOMUNICACIONES` →
`Julio a Diciembre 2026`, a partir del documento de unidades y aportes del curso:
- **U.1 Derivada** (Derivada, Reglas de derivación, Derivación implícita, Aplicaciones de la derivada) y
  **U.2 Integral Indefinida** (Integral indefinida, Métodos de integración, Aplicaciones, Integrales irracionales).
- Tarea 1 → `U1-T1`, Tarea 2 → `U1-T2` (la mayoría de sus temas es de la U.1), Tarea 3 → `U2-T3`.
- 10 estudiantes (`U-29`…`U-38` = Estudiante 1…10 del documento) con sus notas de aportes exactas.
- Sólo tiene Tareas: el middleware pondera sobre los componentes que el curso evaluó (nota = promedio de tareas).

Se ejecuta al final de la siembra automática; para aplicarlo solo:
```bash
docker exec moodle_lms bash /opt/edumonitor_seed/entrypoint-seed.sh --calculo-only
```

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
- `cmendoza`: `U1-T2` = 0 y `U2-T4` = 0 con comentario **SIN ENTREGA**.
- El último estudiante de cada nómina tiene `U2-P3` sin nota, con comentario **PENDIENTE DE REVISIÓN**.

Las tareas calificadas tienen una entrega registrada 1-3 días antes del vencimiento, salvo las de SIN ENTREGA.

## Fechas
Se calculan desde el día en que corre la siembra (23:59, hora de Ecuador) y se re-alinean en cada ejecución:
- **Primer Parcial** (cerrado): cada bloque vence semana a semana; la última actividad venció hace 7 días.
- **Segundo Parcial** (en curso): la primera actividad de cada bloque vence en 7 días y las siguientes cada semana.
- **Supletorio**: vence en 6 semanas.

Para mover el calendario a la fecha actual basta con volver a ejecutar la siembra.

## Identidad visual
CSS inyectado en `additionalhtmlhead`, en azul institucional `#11297A` y blanco: barra superior blanca con filete azul,
pestañas del curso subrayadas en azul, secciones en tarjetas blancas con borde `#DEE2E6` y títulos en azul.
La página de inicio es "Mis cursos".

## Web Services
Servicio `EduMonitor_WS` (REST) con token = `MOODLE_TOKEN` del `.env`. El token debe ser alfanumérico
(Moodle quita los demás caracteres del `wstoken`).
