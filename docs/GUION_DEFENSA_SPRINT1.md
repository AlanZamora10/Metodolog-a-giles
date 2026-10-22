# Guion Oficial de Defensa: Sprint 1
## Capa Inteligente de Seguimiento Académico para Moodle (Middleware + Agente IA)

**Institución:** Universidad Técnica de Ambato (UTA) — FISEI  
**Carrera:** Ingeniería de Software  
**Asignatura:** Metodologías Ágiles  
**Docente:** Ing. Hernán Naranjo, Mg.  
**Equipo:**
- **Alan Zamora:** Scrum Master y Developer (Calidad y CI/CD)
- **Justin Ojeda:** Developer (Repositorio Git, Docker y Backend)
- **Johan Borja:** Developer (Arquitectura, Base de Datos y HU-01)
- **Alvaro Moreta:** Proxy-PO y Developer (Frontend y UX Minimalista)

---

## 1. Orden de Intervención y Tiempos Estimados (Total: ~8 a 10 minutos)

```text
[00:00 - 01:30] Alan Zamora   -> Introducción, Metodología Scrum y CI/CD (Pytest)
[01:30 - 03:30] Justin Ojeda  -> Repositorio Git, Arquitectura Microservicios y Docker
[03:30 - 06:00] Johan Borja   -> Esquema Base de Datos (Postgres), HU-01 y Casos Críticos
[06:00 - 08:30] Alvaro Moreta -> Demostración Web Minimalista, Detalle, Refuerzos y Roles
[08:30 - 10:00] Preguntas y Cierre con el Docente
```

---

## 2. Guion Detallado por Integrante

### Parte 1: Alan Zamora (Scrum Master & Calidad)
> **Tiempo:** 1:30 min  
> **Objetivo:** Abrir con autoridad metodológica, explicar el Sprint 1 y demostrar la calidad de software con pruebas automatizadas.

#### Lo que debes decir (Palabra por palabra):
> *"Buenas tardes, Ingeniero Hernán Naranjo. El día de hoy venimos a presentar la entrega correspondiente al **Sprint 1: Envisioning, diseño y entorno base** de nuestro proyecto: 'Capa Inteligente de Seguimiento Académico para Moodle'.*
>
> *Como equipo Scrum, dividimos el trabajo de acuerdo a la matriz de responsabilidades planificada: Justin en backend y Docker, Johan en base de datos y arquitectura, Alvaro en interfaz minimalista y mi persona facilitando las ceremonias y liderando el aseguramiento de la calidad.*
>
> *Para este Sprint 1 no solo nos enfocamos en el diseño, sino en cumplir estrictamente la Definición de Hecho (DoD). Implementamos Integración Continua con **GitHub Actions**, donde cada commit ejecuta análisis estático con linter y pruebas automatizadas con **Pytest**.*
>
> *Para demostrar la robustez del código, en este momento voy a ejecutar la suite de pruebas unitarias que valida la fórmula oficial de notas de la UTA (40/30/30), la normalización de IDs de Moodle y los endpoints de la API."*

#### Acción en la computadora:
1. Abre la terminal PowerShell en la raíz (`D:\Metodologias Agiles\MoodleProyecto`).
2. Escribe y ejecuta:
   ```powershell
   py -m pytest
   ```
3. Señala la pantalla y di:
   > *"Como puede observar, Ingeniero, tenemos **21 pruebas unitarias pasando al 100% en menos de 5 segundos**, garantizando que el sistema es estable y libre de regresiones."*

---

### Parte 2: Justin Ojeda (Backend & Docker)
> **Tiempo:** 2:00 min  
> **Objetivo:** Explicar la arquitectura de microservicios, el control de versiones en GitHub y la contenedorización.

#### Lo que debes decir:
> *"Buenas tardes, Ingeniero. Continuando con la infraestructura técnica, estructuramos el repositorio con una **arquitectura desacoplada de microservicios**. Esto responde directamente a una de las restricciones críticas del proyecto: evitar que los procesos analíticos o la inferencia de inteligencia artificial saturen el servidor Moodle de la universidad.*
>
> *Organizamos el proyecto en cinco módulos independientes:*
> 1. *`/middleware`: Nuestro servicio central en Python 3.11 con FastAPI, encargado de la sincronización segura por Web Services y cálculo oficial de notas.*
> 2. *`/agent`: Microservicio de análisis que consume Ollama con modelos SLM livianos.*
> 3. *`/database`: Scripts de inicialización SQL relacional.*
> 4. *`/frontend`: Interfaz web minimalista servida en Nginx.*
> 5. *`/docker`: Archivos de configuración y `docker-compose.yml`.*
>
> *Todos los cambios fueron versionados mediante ramas y commits atómicos con la convención Conventional Commits, ya sincronizados en nuestro repositorio de GitHub.*
>
> *En nuestro `docker-compose.yml` dejamos orquestados los contenedores para Moodle LMS con MariaDB, nuestra base analítica PostgreSQL, el middleware y el servicio de Ollama configurado específicamente para ejecutarse en CPU y RAM estándar, sin requerir GPUs costosas."*

#### Acción en la computadora:
- Muestra brevemente en pantalla el repositorio de GitHub con los commits o abre el archivo `docker-compose.yml`.

---

### Parte 3: Johan Borja (Arquitectura, Base de Datos y HU-01)
> **Tiempo:** 2:30 min  
> **Objetivo:** Explicar el modelo relacional en PostgreSQL y ejecutar la validación formal de la Historia de Usuario HU-01.

#### Lo que debes decir:
> *"Buenas tardes, Ingeniero. En la capa de datos, diseñamos un esquema relacional propio en **PostgreSQL** plasmado en `database/init.sql`. Diseñamos una base analítica independiente porque Moodle organiza sus actividades por cursos y secciones, pero no entrega de forma directa la unidad temática ni la fórmula ponderada institucional.*
>
> *Nuestro esquema soporta: materias, periodos académicos divididos en 2 parciales, categorías de unidad (Unidad 1 a 4), calificaciones por componente (Autónomo 40%, Tareas 30% y PAE 30%), tabla de registros y auditoría (HU-16) y tabla de alertas tempranas (HU-08).*
>
> *Para cumplir con la **HU-01 (Curso simulado en Moodle)**, desarrollamos un script ejecutable que valida los criterios de aceptación en formato Gherkin:*
> - *2 materias simulación (Metodologías Ágiles e Ingeniería de Software).*
> - *7 estudiantes de muestra (U-03 a U-09).*
> - *Convención de ID number normalizado en cada actividad: `[MATERIA]-[PARCIAL]-[UNIDAD]-[TEMA]`.*
> - *Y el criterio fundamental: **al menos 2 estudiantes deben tener nota ponderada menor a 5.0** para probar que los promedios generales ocultan situaciones críticas individuales.*
>
> *Voy a ejecutar el script en consola para verificarlo en vivo."*

#### Acción en la computadora:
1. En la misma terminal de PowerShell ejecuta:
   ```powershell
   py scripts/seed_moodle_course.py
   ```
2. Señala la tabla que aparece en la consola y explica:
   > *"Como se evidencia en la salida: las materias, parciales, unidades y actividades cumplen con 'OK'. El promedio del curso es 6.67, pero gracias a la ponderación exacta detectamos que **Estudiante C tiene 3.50** y **Estudiante D tiene 4.50**, ambos en semáforo **CRÍTICO**, mientras que Estudiante F está **EN RIESGO con 6.20**. Con esto la HU-01 queda formalmente validada y aceptada."*

---

### Parte 4: Alvaro Moreta (Frontend & UX / Proxy-PO)
> **Tiempo:** 2:30 min  
> **Objetivo:** Demostrar la interfaz web minimalista en el navegador, el flujo de alertas/refuerzos y la diferenciación de roles (HU-14).

#### Lo que debes decir:
> *"Buenas tardes, Ingeniero. En el frontend trabajamos bajo los principios de **diseño minimalista** establecidos en el informe: fondo limpio, tipografía nativa del sistema, la paleta institucional de la UTA con azul marino `#11297A` y semáforos pedagógicos bien definidos para que el docente identifique los problemas en menos de 3 segundos sin sobrecarga cognitiva.*
>
> *Voy a abrir la aplicación en el navegador para mostrarle los tres mockups planificados más el módulo de autenticación y roles de la **HU-14**."*

#### Acción en la computadora (Navegador con `frontend/index.html`):

1. **Pantalla 1 - Panel General:**
   > *"Aquí tenemos la **Pantalla 1**. En las tarjetas superiores vemos el promedio general (6.40), pero inmediatamente resaltamos en rojo los **2 Estudiantes Críticos** y en naranja el estudiante **En Riesgo**. La tabla inferior desglosa a los 7 alumnos matriculados con su evolución pedagógica."*

2. **Pantalla 2 - Detalle del Estudiante:**
   - Haz clic sobre la fila de **Estudiante C**.
   > *"Al hacer clic en Estudiante C, pasamos a la **Pantalla 2**. El sistema destaca su nota crítica de **3.5 / 10** y una probabilidad de aprobación de solo el 22%. La gráfica de curva temporal muestra cómo sus notas cayeron en las tareas 2 y 3.*
   >
   > *En el desglose de unidades temáticas vemos con barra roja que su punto de quiebre es la **Unidad 2: Lógica y Modelado (2.0 / 10)**, específicamente en diagramación. En la parte inferior, la tarjeta azul presenta la conclusión del **Agente IA** recomendando una tarea práctica de recuperación."*

3. **Pantalla 3 - Alertas y Refuerzos:**
   - Haz clic en el botón blanco **"Generar Tarea de Refuerzo"**.
   > *"Pasamos a la **Pantalla 3**. El docente tiene a la izquierda la bandeja de alertas tempranas y a la derecha la tarea de refuerzo generada. El docente revisa las instrucciones y, como el sistema garantiza control pedagógico, la tarea solo se publica si el profesor da clic en el botón. Al hacer clic en **'Aprobar y Publicar en Moodle'**, la interfaz confirma la publicación."*

4. **Diferenciación de Roles (HU-14):**
   - Haz clic en **"Cambiar Usuario"** y selecciona **"🎓 Estudiante C"**.
   > *"Finalmente, implementamos control de acceso por roles. Si quien inicia sesión es el **Estudiante**, el sistema oculta el panel general y le presenta su **Portal del Estudiante**, donde visualiza exclusivamente sus falencias en la Unidad 2 y el buzón para entregar la tarea de refuerzo que le envió su profesor."*

---

## 3. Cierre Conjunto (Alan Zamora)
> *"Con esto, Ingeniero Hernán Naranjo, demostramos que el **Sprint 1** se encuentra 100% completado, ejecutable, probado y alineado con los requerimientos de la asignatura de Metodologías Ágiles. Quedamos atentos a sus preguntas y retroalimentación."*

---

## 4. Banco de Preguntas Trampa del Docente y Respuestas Blindadas

### Pregunta 1: *"¿Por qué no consumen las notas directamente de la base de datos de Moodle en vez de crear una base PostgreSQL aparte?"*
- **Respuesta:**  
  *"Ingeniero, por dos razones de arquitectura de software: primero, **desacoplamiento y seguridad**. La base de datos de producción de Moodle no debe ser expuesta a consultas analíticas pesadas que puedan degradar el servicio a los estudiantes. Segundo, **modelo de dominio**. Moodle estructura los datos por libros de calificación genéricos; nuestra base analítica almacena el modelo de datos pedagógico específico de la UTA con categorías por unidad y ponderación oficial 40/30/30."*

### Pregunta 2: *"¿Cómo sabe el sistema a qué unidad temática corresponde cada tarea si Moodle solo las divide por semanas o tópicos?"*
- **Respuesta:**  
  *"Aplicamos el principio de **'Convención sobre Configuración'**. Establecimos una convención normalizada en el campo `ID number` de cada actividad en Moodle con la estructura `[MATERIA]-[PARCIAL]-[UNIDAD]-[TEMA]` (por ejemplo `MAT1-P1-U2-T3`). Nuestro parser en Python valida este patrón; si una tarea no cumple la convención, la clasifica en los logs de auditoría como 'sin clasificar' conforme a la HU-04 y HU-16."*

### Pregunta 3: *"¿Cuánto cuesta la API de inteligencia artificial que están usando?"*
- **Respuesta:**  
  *"**Cero dólares**. Una de las restricciones del proyecto es operar con herramientas libres. El agente corre en un contenedor Docker con **Ollama** utilizando modelos SLM ligeros como `llama3.2:1b`, diseñados para ejecutarse en CPU sin requerir tarjetas gráficas dedicadas. Además, contamos con un motor heurístico de respaldo que responde en menos de 10 segundos en caso de timeout (HU-11B)."*

### Pregunta 4: *"¿Cómo calcularon la tendencia de las notas en la gráfica?"*
- **Respuesta:**  
  *"Utilizamos la fórmula clásica de **regresión lineal simple** sobre las notas de las tareas. Si la pendiente es mayor a +0.25 se clasifica como 'Sube', si es menor a -0.25 se cataloga como 'Baja' (tendencia descendente crítica), y si se mantiene en el rango se etiqueta como 'Estable'."*

---

## 5. Hoja de Comandos para la Presentación (Copiar y Pegar)

```powershell
# Paso 1: Asegurarse de estar en la carpeta raíz
cd "D:\Metodologias Agiles\MoodleProyecto"

# Paso 2: Ejecutar las 21 pruebas automáticas (Alan Zamora)
py -m pytest

# Paso 3: Ejecutar la verificación de datos HU-01 (Johan Borja)
py scripts/seed_moodle_course.py

# Paso 4: Abrir la interfaz web (Alvaro Moreta)
# Abrir directamente en el navegador el archivo:
# D:\Metodologias Agiles\MoodleProyecto\frontend\index.html
```
