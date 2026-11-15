"""
Contenidos de refuerzo por materia y unidad (FISEI · Software, período Julio a Diciembre 2026).

Alimentan la guía de estudio en PDF que se adjunta a cada tarea de refuerzo: explicación conceptual de los
temas, un ejemplo resuelto paso a paso y ejercicios propuestos. Es contenido determinista y revisable por el
docente (no lo genera el modelo de lenguaje), por lo que no puede inventar datos del estudiante.

Claves: la sigla del curso en Moodle (SOF-POO-A -> "POO") y el número de unidad (1 a 4).
"""

from typing import Any, Dict, Optional

Unidad = Dict[str, Any]

CONTENIDOS: Dict[str, Dict[int, Unidad]] = {
    # ------------------------------------------------------------------ Programación orientada a objetos
    "POO": {
        1: {
            "titulo": "Fundamentos de la programación orientada a objetos",
            "temas": [
                ("Clases y objetos",
                 "Una clase es el molde que define qué datos (atributos) y qué comportamiento (métodos) tendrán sus "
                 "objetos. Un objeto es una instancia concreta de esa clase, con valores propios en sus atributos."),
                ("Atributos, métodos y constructores",
                 "Los atributos guardan el estado del objeto; los métodos lo consultan o lo modifican. El constructor "
                 "inicializa el objeto en un estado válido en el momento de crearlo."),
                ("Encapsulamiento",
                 "Los atributos se declaran privados y se exponen sólo mediante métodos públicos que validan los "
                 "cambios. Así el objeto protege sus reglas internas (por ejemplo, que un saldo nunca sea negativo)."),
            ],
            "ejemplo": {
                "enunciado": "Implemente la clase CuentaBancaria con saldo privado y los métodos depositar(monto) y "
                             "retirar(monto), impidiendo montos negativos y retiros mayores al saldo.",
                "pasos": [
                    "Declarar el atributo privado saldo (double) y un constructor que lo inicialice en 0.",
                    "depositar(monto): si monto <= 0 lanzar IllegalArgumentException; si no, saldo = saldo + monto.",
                    "retirar(monto): validar monto > 0 y monto <= saldo; si se cumple, saldo = saldo - monto.",
                    "Exponer getSaldo() sin setter público: el saldo sólo cambia mediante operaciones válidas.",
                    "Probar: crear la cuenta, depositar 100, retirar 30 y verificar que getSaldo() devuelve 70.",
                ],
                "resultado": "El saldo final es 70.00 y un retiro de 200 es rechazado sin alterar el estado.",
            },
            "ejercicios": [
                "Modele la clase Estudiante (cédula, nombres, notas) con constructor y método promedio().",
                "Agregue validaciones a Estudiante para que ninguna nota quede fuera del rango 0 a 10.",
                "Cree tres objetos Estudiante y muestre el de mayor promedio usando sólo métodos públicos.",
                "Explique con sus palabras por qué el atributo notas no debe ser público.",
            ],
        },
        2: {
            "titulo": "Herencia y polimorfismo",
            "temas": [
                ("Herencia",
                 "Una subclase reutiliza atributos y métodos de su superclase (extends) y agrega o especializa "
                 "comportamiento. Debe cumplirse la relación «es un»: un Círculo es una Figura."),
                ("Sobrescritura y clases abstractas",
                 "Una clase abstracta declara métodos sin implementación (abstract) que cada subclase debe "
                 "sobrescribir (@Override). No se pueden crear objetos de una clase abstracta."),
                ("Polimorfismo",
                 "Una variable del tipo de la superclase puede referenciar objetos de cualquier subclase; al invocar "
                 "un método se ejecuta la versión de la clase real del objeto (enlace dinámico)."),
            ],
            "ejemplo": {
                "enunciado": "Defina la clase abstracta Figura con area() y las subclases Circulo y Rectangulo; calcule "
                             "el área total de una lista mixta de figuras.",
                "pasos": [
                    "abstract class Figura { abstract double area(); }",
                    "Circulo extends Figura: atributo radio; area() devuelve Math.PI * radio * radio.",
                    "Rectangulo extends Figura: atributos base y altura; area() devuelve base * altura.",
                    "Crear List<Figura> con new Circulo(1) y new Rectangulo(2, 3).",
                    "Recorrer la lista sumando f.area(): cada objeto ejecuta su propia implementación.",
                ],
                "resultado": "Área total = 3.1416 + 6.0000 = 9.1416, sin usar instanceof ni condicionales por tipo.",
            },
            "ejercicios": [
                "Agregue la subclase Triangulo a la jerarquía de Figura sin modificar el código del recorrido.",
                "Modele Empleado (abstracta) con calcularSueldo() y las subclases EmpleadoFijo y EmpleadoPorHoras.",
                "Calcule la nómina total de una lista de empleados aplicando polimorfismo.",
                "Indique qué ocurre si una subclase no implementa un método abstracto y por qué.",
            ],
        },
        3: {
            "titulo": "Interfaces, colecciones y genéricos",
            "temas": [
                ("Interfaces",
                 "Una interfaz define un contrato (métodos que una clase se compromete a implementar). Una clase puede "
                 "implementar varias interfaces, lo que desacopla el código de las clases concretas."),
                ("Colecciones",
                 "List mantiene el orden y admite duplicados; Set no admite duplicados; Map asocia claves con valores. "
                 "Elegir la colección correcta simplifica búsquedas y evita errores."),
                ("Genéricos",
                 "Los genéricos (List<Estudiante>) permiten que el compilador verifique el tipo de los elementos y "
                 "eliminan conversiones (casts) inseguras."),
            ],
            "ejemplo": {
                "enunciado": "Cree la interfaz Pagable con montoAPagar() e impleméntela en Factura y Empleado; sume lo "
                             "que la empresa debe pagar.",
                "pasos": [
                    "interface Pagable { double montoAPagar(); }",
                    "Factura implements Pagable: montoAPagar() devuelve cantidad * precioUnitario.",
                    "Empleado implements Pagable: montoAPagar() devuelve su sueldo mensual.",
                    "Guardar los objetos en List<Pagable> pagos = new ArrayList<>();",
                    "Sumar con un for-each: total += p.montoAPagar();",
                ],
                "resultado": "Con una factura de 2 x 50 y un empleado de 800, el total es 900.00.",
            },
            "ejercicios": [
                "Use un Map<String, Estudiante> indexado por cédula y busque un estudiante en tiempo constante.",
                "Implemente Comparable en Estudiante para ordenar una lista por promedio descendente.",
                "Elimine de un Set los correos duplicados de una lista de contactos.",
                "Explique la diferencia entre una clase abstracta y una interfaz con un ejemplo propio.",
            ],
        },
        4: {
            "titulo": "Excepciones y buenas prácticas de diseño",
            "temas": [
                ("Manejo de excepciones",
                 "try/catch/finally separa el flujo normal del tratamiento de errores. Se capturan las excepciones "
                 "que se pueden resolver y se propagan (throws) las que debe manejar quien llama."),
                ("Excepciones personalizadas",
                 "Crear una excepción propia (extends Exception) comunica errores del dominio con un nombre claro, "
                 "por ejemplo SaldoInsuficienteException."),
                ("Principios SOLID básicos",
                 "Responsabilidad única: cada clase tiene un solo motivo de cambio. Abierto/cerrado: se extiende el "
                 "comportamiento con nuevas clases sin modificar las existentes."),
            ],
            "ejemplo": {
                "enunciado": "Haga que retirar(monto) de CuentaBancaria lance SaldoInsuficienteException y trate el "
                             "error en el programa principal.",
                "pasos": [
                    "class SaldoInsuficienteException extends Exception con un constructor que recibe el mensaje.",
                    "void retirar(double monto) throws SaldoInsuficienteException { if (monto > saldo) throw ...; }",
                    "En main: try { cuenta.retirar(500); } catch (SaldoInsuficienteException e) { mostrar mensaje }",
                    "Usar finally para registrar la operación tanto si tuvo éxito como si falló.",
                ],
                "resultado": "El programa informa «Saldo insuficiente» y continúa sin terminar abruptamente.",
            },
            "ejercicios": [
                "Lea números desde teclado y capture NumberFormatException cuando el texto no sea numérico.",
                "Cree NotaFueraDeRangoException y úsela en el método registrarNota del Estudiante.",
                "Identifique una clase de su proyecto con más de una responsabilidad y propóngase dividirla.",
                "Explique cuándo conviene propagar una excepción en lugar de capturarla.",
            ],
        },
    },
    # ------------------------------------------------------------------ Estructura de datos
    "ED": {
        1: {
            "titulo": "Complejidad algorítmica, arreglos y búsqueda",
            "temas": [
                ("Notación Big O",
                 "Describe cómo crece el número de operaciones de un algoritmo según el tamaño n de la entrada: O(1) "
                 "constante, O(log n) logarítmico, O(n) lineal, O(n²) cuadrático."),
                ("Arreglos",
                 "Un arreglo almacena elementos del mismo tipo en posiciones contiguas: el acceso por índice es O(1), "
                 "pero insertar o eliminar en medio exige desplazar elementos, O(n)."),
                ("Búsqueda lineal y binaria",
                 "La búsqueda lineal recorre todo el arreglo, O(n). La binaria exige el arreglo ordenado y descarta la "
                 "mitad en cada paso, O(log n)."),
            ],
            "ejemplo": {
                "enunciado": "Busque el valor 25 en el arreglo ordenado [3, 8, 12, 19, 25, 31, 40] con búsqueda binaria.",
                "pasos": [
                    "inicio = 0, fin = 6 -> medio = 3, arreglo[3] = 19 < 25: se descarta la mitad izquierda, inicio = 4.",
                    "inicio = 4, fin = 6 -> medio = 5, arreglo[5] = 31 > 25: se descarta la mitad derecha, fin = 4.",
                    "inicio = 4, fin = 4 -> medio = 4, arreglo[4] = 25: valor encontrado.",
                ],
                "resultado": "El valor está en la posición 4 y se encontró en 3 comparaciones (lineal necesitaría 5).",
            },
            "ejercicios": [
                "Determine la complejidad de dos ciclos for anidados que recorren un arreglo de tamaño n.",
                "Haga la traza de la búsqueda binaria del valor 7 en [1, 4, 7, 9, 15, 20].",
                "Implemente una función que invierta un arreglo en el mismo espacio y analice su complejidad.",
                "Explique por qué la búsqueda binaria no funciona en un arreglo desordenado.",
            ],
        },
        2: {
            "titulo": "Listas enlazadas, pilas y colas",
            "temas": [
                ("Listas enlazadas",
                 "Cada nodo guarda un dato y la referencia al siguiente. Insertar al inicio es O(1) y no requiere "
                 "desplazar elementos, pero acceder a la posición k exige recorrer k nodos."),
                ("Pilas (LIFO)",
                 "El último elemento en entrar es el primero en salir: push apila, pop desapila y peek consulta la "
                 "cima. Se usan para deshacer acciones, evaluar expresiones y en la recursión."),
                ("Colas (FIFO)",
                 "El primero en entrar es el primero en salir: enqueue agrega al final y dequeue retira del frente. "
                 "Modelan turnos de atención, impresión y planificación de procesos."),
            ],
            "ejemplo": {
                "enunciado": "Evalúe la expresión en notación postfija «5 3 + 2 *» usando una pila.",
                "pasos": [
                    "Leer 5 -> push(5). Pila: [5].",
                    "Leer 3 -> push(3). Pila: [5, 3].",
                    "Leer + -> pop() = 3, pop() = 5, push(5 + 3 = 8). Pila: [8].",
                    "Leer 2 -> push(2). Pila: [8, 2].",
                    "Leer * -> pop() = 2, pop() = 8, push(8 * 2 = 16). Pila: [16].",
                ],
                "resultado": "Al terminar la expresión la pila contiene un solo valor: 16.",
            },
            "ejercicios": [
                "Implemente una pila con lista enlazada y los métodos push, pop, peek y estaVacia.",
                "Verifique con una pila si los paréntesis de «(a + [b * c]) - {d}» están balanceados.",
                "Simule una cola de atención con 5 clientes y muestre el orden en que son atendidos.",
                "Compare el costo de eliminar el primer elemento en un arreglo y en una lista enlazada.",
            ],
        },
        3: {
            "titulo": "Árboles binarios de búsqueda",
            "temas": [
                ("Árbol binario de búsqueda (ABB)",
                 "Cada nodo tiene a lo sumo dos hijos; los valores del subárbol izquierdo son menores y los del derecho "
                 "mayores. Buscar, insertar y eliminar cuestan O(altura)."),
                ("Recorridos",
                 "Inorden (izquierda, raíz, derecha) entrega los valores ordenados; preorden (raíz, izquierda, derecha) "
                 "sirve para copiar el árbol; postorden (izquierda, derecha, raíz) para liberarlo."),
                ("Balanceo",
                 "Si se insertan datos ya ordenados el ABB degenera en una lista (altura n). Los árboles AVL rotan "
                 "nodos para mantener la altura en O(log n)."),
            ],
            "ejemplo": {
                "enunciado": "Inserte 50, 30, 70, 20, 40 y 60 en un ABB vacío y obtenga sus recorridos inorden y preorden.",
                "pasos": [
                    "50 es la raíz. 30 < 50 va a la izquierda; 70 > 50 va a la derecha.",
                    "20 < 50 y 20 < 30: hijo izquierdo de 30. 40 < 50 y 40 > 30: hijo derecho de 30.",
                    "60 > 50 y 60 < 70: hijo izquierdo de 70.",
                    "Inorden: 20, 30, 40, 50, 60, 70 (valores ordenados).",
                    "Preorden: 50, 30, 20, 40, 70, 60.",
                ],
                "resultado": "Árbol de altura 3; el recorrido inorden confirma que la estructura es un ABB válido.",
            },
            "ejercicios": [
                "Inserte 15, 10, 20, 8, 12, 25 en un ABB y dibuje el árbol resultante.",
                "Escriba el recorrido postorden del árbol del ejemplo resuelto.",
                "Elimine el nodo 30 del ejemplo (tiene dos hijos) y explique qué nodo lo reemplaza.",
                "Explique qué ocurre con la altura si se insertan 1, 2, 3, 4, 5 en ese orden.",
            ],
        },
        4: {
            "titulo": "Grafos y algoritmos de ordenamiento",
            "temas": [
                ("Representación de grafos",
                 "Un grafo se representa con una matriz de adyacencia (O(V²) espacio, consulta O(1)) o con listas de "
                 "adyacencia (O(V + E) espacio), más eficientes en grafos dispersos."),
                ("Recorridos BFS y DFS",
                 "BFS recorre por niveles usando una cola y encuentra el camino más corto en grafos no ponderados; "
                 "DFS profundiza usando una pila o recursión."),
                ("Ordenamiento eficiente",
                 "Merge sort divide, ordena y mezcla en O(n log n) siempre; quicksort particiona alrededor de un pivote "
                 "y es O(n log n) en promedio, O(n²) en el peor caso."),
            ],
            "ejemplo": {
                "enunciado": "Recorra con BFS desde A el grafo con aristas A-B, A-C, B-D, C-D, D-E.",
                "pasos": [
                    "Cola: [A]. Visitar A y encolar sus vecinos B y C. Cola: [B, C].",
                    "Visitar B y encolar D (no visitado). Cola: [C, D].",
                    "Visitar C; D ya está en la cola. Cola: [D].",
                    "Visitar D y encolar E. Cola: [E]. Visitar E. Cola vacía.",
                ],
                "resultado": "Orden de visita: A, B, C, D, E. E está a 3 aristas de A (A-B-D-E).",
            },
            "ejercicios": [
                "Escriba la lista de adyacencia del grafo del ejemplo resuelto.",
                "Recorra el mismo grafo con DFS desde A y compare el orden con BFS.",
                "Ordene [38, 27, 43, 3, 9, 82, 10] con merge sort mostrando cada división y mezcla.",
                "Explique cuándo quicksort alcanza su peor caso y cómo evitarlo.",
            ],
        },
    },
    # ------------------------------------------------------------------ Metodologías ágiles
    "MA": {
        1: {
            "titulo": "Fundamentos del desarrollo ágil",
            "temas": [
                ("Manifiesto ágil",
                 "Valora a las personas e interacciones sobre procesos y herramientas, el software funcionando sobre la "
                 "documentación extensa, la colaboración con el cliente sobre la negociación de contratos y la "
                 "respuesta al cambio sobre seguir un plan."),
                ("Los 12 principios",
                 "Entregas frecuentes de software que funciona, cambios bienvenidos incluso tarde, equipos "
                 "autoorganizados, ritmo sostenible y reflexión periódica para mejorar."),
                ("Ágil frente a cascada",
                 "Cascada planifica todo al inicio y entrega al final; el enfoque ágil trabaja en iteraciones cortas "
                 "que entregan valor y se ajustan con la retroalimentación del cliente."),
            ],
            "ejemplo": {
                "enunciado": "Una empresa recibe cambios de requisitos cada dos semanas. Justifique si conviene un "
                             "enfoque ágil o en cascada.",
                "pasos": [
                    "Identificar el contexto: requisitos inestables y cliente disponible para revisar avances.",
                    "Relacionar con el principio «aceptar cambios incluso en etapas tardías».",
                    "Comparar: en cascada cada cambio obliga a rehacer fases ya cerradas (alto costo).",
                    "Concluir con una propuesta: iteraciones de 2 semanas con demostración al cliente al final de cada una.",
                ],
                "resultado": "Se recomienda el enfoque ágil: reduce el costo del cambio y valida el producto cada iteración.",
            },
            "ejercicios": [
                "Explique con un ejemplo propio cada uno de los cuatro valores del manifiesto ágil.",
                "Elija tres de los 12 principios y describa cómo los aplicaría en un proyecto universitario.",
                "Elabore una tabla comparativa ágil frente a cascada (planificación, entregas, cambios, riesgo).",
                "Describa un proyecto en el que un enfoque en cascada sí sería adecuado y por qué.",
            ],
        },
        2: {
            "titulo": "Marco de trabajo Scrum",
            "temas": [
                ("Roles (responsabilidades)",
                 "El Product Owner maximiza el valor y ordena el Product Backlog; el Scrum Master facilita y elimina "
                 "impedimentos; los Developers construyen el incremento y se autoorganizan."),
                ("Eventos",
                 "Sprint (1 a 4 semanas), Sprint Planning, Daily Scrum de 15 minutos, Sprint Review con el cliente y "
                 "Sprint Retrospective para mejorar la forma de trabajo."),
                ("Artefactos",
                 "Product Backlog (todo lo que podría hacerse), Sprint Backlog (lo comprometido en el sprint) e "
                 "Incremento, que debe cumplir la Definición de Terminado."),
            ],
            "ejemplo": {
                "enunciado": "Con una velocidad histórica de 20 puntos, planifique el sprint a partir del backlog: "
                             "Login (8), Registro (5), Reportes (13), Perfil (3), Notificaciones (5).",
                "pasos": [
                    "Respetar el orden de prioridad que define el Product Owner.",
                    "Login (8) -> acumulado 8. Registro (5) -> acumulado 13.",
                    "Reportes (13) superaría la capacidad (26 > 20): no se incluye en este sprint.",
                    "Perfil (3) -> acumulado 16. Notificaciones (5) -> 21 supera la capacidad: queda para el siguiente.",
                    "Redactar el objetivo del sprint: «Permitir que el usuario se registre, ingrese y edite su perfil».",
                ],
                "resultado": "Sprint Backlog: Login, Registro y Perfil (16 puntos), con margen para imprevistos.",
            },
            "ejercicios": [
                "Asigne el rol de Scrum responsable de cada situación: priorizar, eliminar un bloqueo, estimar.",
                "Planifique un sprint de 15 puntos con un backlog propio de al menos 6 historias.",
                "Redacte la agenda de una Sprint Review de 1 hora para un proyecto de su elección.",
                "Proponga una Definición de Terminado de 5 criterios para un equipo de desarrollo web.",
            ],
        },
        3: {
            "titulo": "Historias de usuario y estimación",
            "temas": [
                ("Historias de usuario",
                 "Formato: «Como <rol>, quiero <funcionalidad>, para <beneficio>». Deben cumplir INVEST: "
                 "independientes, negociables, valiosas, estimables, pequeñas y comprobables."),
                ("Criterios de aceptación",
                 "Condiciones verificables para dar por cumplida la historia, por ejemplo en formato Dado / Cuando / "
                 "Entonces (Gherkin)."),
                ("Estimación relativa",
                 "Los puntos de historia comparan esfuerzo, complejidad e incertidumbre. En Planning Poker cada "
                 "miembro estima con la serie de Fibonacci y se conversa hasta llegar a consenso."),
            ],
            "ejemplo": {
                "enunciado": "Redacte una historia de usuario con criterios de aceptación para recuperar la contraseña.",
                "pasos": [
                    "Historia: «Como estudiante, quiero recuperar mi contraseña por correo, para volver a ingresar "
                    "al aula virtual».",
                    "Criterio 1: Dado un correo registrado, cuando solicito recuperar, entonces recibo un enlace válido "
                    "por 30 minutos.",
                    "Criterio 2: Dado un correo no registrado, cuando solicito recuperar, entonces veo un mensaje "
                    "genérico sin revelar si existe.",
                    "Verificar INVEST: es pequeña, valiosa y comprobable por sus criterios.",
                    "Estimar en Planning Poker: votos 3, 5, 5, 8 -> se discute el 8 y se acuerda 5 puntos.",
                ],
                "resultado": "Historia lista para el sprint: redactada, con 2 criterios verificables y estimada en 5 puntos.",
            },
            "ejercicios": [
                "Escriba 3 historias de usuario para un sistema de matrícula universitaria.",
                "Agregue a cada historia dos criterios de aceptación en formato Dado / Cuando / Entonces.",
                "Divida la historia «Como docente quiero gestionar mis cursos» en historias más pequeñas.",
                "Explique por qué se estima en puntos relativos y no directamente en horas.",
            ],
        },
        4: {
            "titulo": "Kanban, métricas y mejora continua",
            "temas": [
                ("Kanban",
                 "Visualiza el flujo de trabajo en columnas (Por hacer, En progreso, Hecho) y limita el trabajo en "
                 "curso (WIP) para terminar antes de empezar tareas nuevas."),
                ("Métricas ágiles",
                 "Velocidad (puntos completados por sprint), burndown (trabajo restante frente al tiempo) y lead time "
                 "(tiempo desde que se pide una tarea hasta que se entrega)."),
                ("Retrospectiva",
                 "Al final de cada sprint el equipo analiza qué salió bien, qué mejorar y define acciones concretas "
                 "con responsable para el siguiente sprint."),
            ],
            "ejemplo": {
                "enunciado": "Un equipo completó 18, 22 y 20 puntos en los últimos tres sprints. Estime cuántos sprints "
                             "necesita para un backlog restante de 120 puntos.",
                "pasos": [
                    "Velocidad promedio = (18 + 22 + 20) / 3 = 20 puntos por sprint.",
                    "Sprints necesarios = 120 / 20 = 6 sprints.",
                    "Con sprints de 2 semanas, la duración estimada es de 12 semanas.",
                    "Revisar la estimación en cada sprint, porque la velocidad real puede cambiar.",
                ],
                "resultado": "Se proyectan 6 sprints (unas 12 semanas) con la velocidad promedio de 20 puntos.",
            },
            "ejercicios": [
                "Diseñe un tablero Kanban para su proyecto con al menos 4 columnas y límites WIP justificados.",
                "Dibuje el burndown ideal de un sprint de 10 días con 40 puntos comprometidos.",
                "Calcule la velocidad promedio de un equipo que completó 12, 15, 9 y 16 puntos.",
                "Proponga una dinámica de retrospectiva y tres acciones de mejora concretas.",
            ],
        },
    },
    # ------------------------------------------------------------------ Manejo y configuración del software
    "MCS": {
        1: {
            "titulo": "Gestión de la configuración y control de versiones",
            "temas": [
                ("Gestión de la configuración del software (GCS)",
                 "Identifica, controla y audita los elementos de configuración (código, documentos, scripts) para "
                 "saber en todo momento qué versión de cada uno forma parte del producto."),
                ("Línea base",
                 "Es una versión revisada y aprobada de un conjunto de elementos que sólo cambia mediante un "
                 "procedimiento formal de control de cambios."),
                ("Control de versiones con Git",
                 "Git registra instantáneas (commits) del repositorio. Flujo básico: modificar en el directorio de "
                 "trabajo, preparar con git add y confirmar con git commit."),
            ],
            "ejemplo": {
                "enunciado": "Cree un repositorio para un proyecto nuevo y registre dos versiones de un archivo.",
                "pasos": [
                    "git init -> crea el repositorio local (carpeta .git).",
                    "Crear README.md y ejecutar git add README.md -> el archivo pasa al área de preparación.",
                    "git commit -m \"docs: crea README inicial\" -> primera versión confirmada.",
                    "Editar README.md, revisar con git diff y confirmar con git commit -am \"docs: agrega instalación\".",
                    "git log --oneline -> muestra los dos commits con su identificador abreviado.",
                ],
                "resultado": "El historial conserva ambas versiones y permite volver a cualquiera con git checkout.",
            },
            "ejercicios": [
                "Enumere 6 elementos de configuración de un proyecto web y su responsable.",
                "Explique la diferencia entre el directorio de trabajo, el área de preparación y el repositorio.",
                "Cree un repositorio con 3 commits de mensajes descriptivos y entregue la salida de git log.",
                "Describa qué es una línea base y cuándo la establecería en su proyecto.",
            ],
        },
        2: {
            "titulo": "Ramas, fusiones y resolución de conflictos",
            "temas": [
                ("Ramas",
                 "Una rama es una línea de desarrollo independiente. Permite trabajar en una funcionalidad sin afectar "
                 "la rama principal hasta que esté lista (git switch -c feature/login)."),
                ("Estrategias de ramificación",
                 "Git Flow separa main, develop, feature, release y hotfix; trunk-based mantiene ramas muy cortas que "
                 "se integran a la principal varias veces al día."),
                ("Fusiones y conflictos",
                 "git merge integra los cambios de otra rama. Si dos ramas modifican las mismas líneas, Git marca un "
                 "conflicto que el desarrollador resuelve manualmente antes de confirmar."),
            ],
            "ejemplo": {
                "enunciado": "Dos desarrolladores cambiaron la misma línea de config.py. Resuelva el conflicto al fusionar "
                             "feature/puerto en develop.",
                "pasos": [
                    "git switch develop y git merge feature/puerto -> Git informa CONFLICT en config.py.",
                    "Abrir config.py: entre <<<<<<< y ======= está la versión de develop; entre ======= y >>>>>>> la "
                    "de la rama.",
                    "Acordar con el equipo el valor correcto (PUERTO = 8080) y borrar las marcas de conflicto.",
                    "git add config.py y git commit para concluir la fusión.",
                    "Ejecutar las pruebas antes de publicar con git push.",
                ],
                "resultado": "develop integra la funcionalidad con un único valor de PUERTO y un historial trazable.",
            },
            "ejercicios": [
                "Cree una rama feature, haga 2 commits y fusiónela en develop; entregue el historial gráfico.",
                "Provoque un conflicto en un repositorio de práctica y documente cómo lo resolvió.",
                "Compare git merge y git rebase: ventajas, riesgos y cuándo usar cada uno.",
                "Proponga la estrategia de ramas para un equipo de 4 personas y justifíquela.",
            ],
        },
        3: {
            "titulo": "Integración continua y versionado",
            "temas": [
                ("Integración continua (CI)",
                 "Cada cambio que llega al repositorio se compila y se prueba automáticamente en un pipeline; los "
                 "errores se detectan en minutos y no al final del proyecto."),
                ("Pruebas automatizadas en el pipeline",
                 "Las etapas típicas son instalar dependencias, analizar el código (lint), ejecutar pruebas unitarias "
                 "y construir el artefacto. Si una etapa falla, el cambio no se integra."),
                ("Versionado semántico",
                 "MAYOR.MENOR.PARCHE: se incrementa MAYOR con cambios incompatibles, MENOR con funcionalidades "
                 "compatibles y PARCHE con correcciones de errores."),
            ],
            "ejemplo": {
                "enunciado": "La versión actual es 2.4.1. Determine la nueva versión tras cada cambio publicado por separado.",
                "pasos": [
                    "Se corrige un error de cálculo sin cambiar la interfaz -> PARCHE: 2.4.2.",
                    "Se agrega un reporte nuevo compatible con lo existente -> MENOR: 2.5.0 (el parche vuelve a 0).",
                    "Se elimina un endpoint que usaban los clientes -> MAYOR: 3.0.0 (menor y parche vuelven a 0).",
                ],
                "resultado": "Secuencia de publicación: 2.4.2 -> 2.5.0 -> 3.0.0.",
            },
            "ejercicios": [
                "Diseñe las etapas de un pipeline de CI para un proyecto Python o JavaScript.",
                "Indique la versión resultante de 1.9.3 tras: corrección, nueva función y cambio incompatible.",
                "Explique qué debe hacer el equipo cuando el pipeline falla en la rama principal.",
                "Escriba un archivo de configuración de CI básico (por ejemplo, GitHub Actions) con lint y pruebas.",
            ],
        },
        4: {
            "titulo": "Control de cambios, auditoría y entrega",
            "temas": [
                ("Control de cambios",
                 "Toda modificación a una línea base se solicita formalmente, se analiza su impacto, la aprueba un "
                 "comité y se implementa y verifica de forma trazable."),
                ("Auditoría de la configuración",
                 "Comprueba que el producto entregado coincide con lo documentado (auditoría física) y que cumple los "
                 "requisitos aprobados (auditoría funcional)."),
                ("Gestión de entregas (releases)",
                 "Una entrega agrupa cambios aprobados, se etiqueta en el repositorio (git tag v2.0.0) y se acompaña "
                 "de notas de versión y un plan de despliegue y reversión."),
            ],
            "ejemplo": {
                "enunciado": "El cliente pide agregar un campo «cédula» al formulario de registro ya en producción. "
                             "Aplique el proceso de control de cambios.",
                "pasos": [
                    "Registrar la solicitud de cambio (SC-014) con descripción, solicitante y justificación.",
                    "Analizar el impacto: base de datos, formulario, validaciones, pruebas y documentación.",
                    "Presentar el análisis al comité de control de cambios y obtener la aprobación.",
                    "Implementar en una rama, probar, fusionar y etiquetar la nueva versión (v1.3.0).",
                    "Actualizar la línea base y cerrar la SC-014 con la evidencia de verificación.",
                ],
                "resultado": "El cambio queda trazable desde la solicitud hasta la versión que lo contiene.",
            },
            "ejercicios": [
                "Elabore un formato de solicitud de cambio con todos sus campos obligatorios.",
                "Realice el análisis de impacto de cambiar el método de autenticación de un sistema.",
                "Redacte las notas de versión de una entrega con 3 mejoras y 2 correcciones.",
                "Diferencie la auditoría física de la funcional con un ejemplo de cada una.",
            ],
        },
    },
}


def sigla_curso(shortname: str) -> str:
    """'SOF-POO-A' -> 'POO'."""
    partes = [p for p in (shortname or "").upper().split("-") if p and p != "SOF"]
    return partes[0] if partes else (shortname or "").upper()


def contenido_unidad(shortname: str, unidad: int) -> Optional[Unidad]:
    """Contenido de la materia y unidad; None si la materia no está en el catálogo."""
    materia = CONTENIDOS.get(sigla_curso(shortname))
    if not materia:
        return None
    return materia.get(unidad) or materia.get(min(materia, key=lambda u: abs(u - unidad)))
