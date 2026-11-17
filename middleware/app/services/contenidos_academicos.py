"""
Contenidos de refuerzo por materia y unidad (FISEI · Software, período Julio a Diciembre 2026).

Alimentan la guía de estudio en PDF que se adjunta a cada tarea de refuerzo: explicación conceptual de los
temas, un ejemplo resuelto paso a paso y ejercicios propuestos. Es contenido determinista y revisable por el
docente (no lo genera el modelo de lenguaje), por lo que no puede inventar datos del estudiante.

Claves: la sigla del curso en Moodle (SOF-POO-A => "POO") y el número de unidad (1 a 4).
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
                    "inicio = 0, fin = 6 => medio = 3, arreglo[3] = 19 < 25: se descarta la mitad izquierda, inicio = 4.",
                    "inicio = 4, fin = 6 => medio = 5, arreglo[5] = 31 > 25: se descarta la mitad derecha, fin = 4.",
                    "inicio = 4, fin = 4 => medio = 4, arreglo[4] = 25: valor encontrado.",
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
                "enunciado": "Evalúe la expresión en notación postfija '5 3 + 2 *' usando una pila.",
                "pasos": [
                    "Leer 5 => push(5). Pila: [5].",
                    "Leer 3 => push(3). Pila: [5, 3].",
                    "Leer + => pop() = 3, pop() = 5, push(5 + 3 = 8). Pila: [8].",
                    "Leer 2 => push(2). Pila: [8, 2].",
                    "Leer * => pop() = 2, pop() = 8, push(8 * 2 = 16). Pila: [16].",
                ],
                "resultado": "Al terminar la expresión la pila contiene un solo valor: 16.",
            },
            "ejercicios": [
                "Implemente una pila con lista enlazada y los métodos push, pop, peek y estaVacia.",
                "Verifique con una pila si los paréntesis de '(a + [b * c]) - {d}' están balanceados.",
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
                    "Login (8) => acumulado 8. Registro (5) => acumulado 13.",
                    "Reportes (13) superaría la capacidad (26 > 20): no se incluye en este sprint.",
                    "Perfil (3) => acumulado 16. Notificaciones (5) => 21 supera la capacidad: queda para el siguiente.",
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
                 "Formato: 'Como <rol>, quiero <funcionalidad>, para <beneficio>'. Deben cumplir INVEST: "
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
                    "Estimar en Planning Poker: votos 3, 5, 5, 8 => se discute el 8 y se acuerda 5 puntos.",
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
                    "git init => crea el repositorio local (carpeta .git).",
                    "Crear README.md y ejecutar git add README.md => el archivo pasa al área de preparación.",
                    "git commit -m \"docs: crea README inicial\" => primera versión confirmada.",
                    "Editar README.md, revisar con git diff y confirmar con git commit -am \"docs: agrega instalación\".",
                    "git log --oneline => muestra los dos commits con su identificador abreviado.",
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
                    "git switch develop y git merge feature/puerto => Git informa CONFLICT en config.py.",
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
                    "Se corrige un error de cálculo sin cambiar la interfaz => PARCHE: 2.4.2.",
                    "Se agrega un reporte nuevo compatible con lo existente => MENOR: 2.5.0 (el parche vuelve a 0).",
                    "Se elimina un endpoint que usaban los clientes => MAYOR: 3.0.0 (menor y parche vuelven a 0).",
                ],
                "resultado": "Secuencia de publicación: 2.4.2 => 2.5.0 => 3.0.0.",
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
    # ------------------------------------------------------------------ Ingeniería de Software I
    "IS1": {
        1: {
            "titulo": "Procesos de software y ciclo de vida",
            "temas": [
                ("Proceso de software",
                 "Conjunto de actividades para producir software: especificación, diseño e implementación, validación "
                 "y evolución. Cada organización lo adapta a su contexto."),
                ("Modelos de ciclo de vida",
                 "Cascada (fases secuenciales), incremental (entregas parciales que suman funcionalidad) y espiral "
                 "(iteraciones guiadas por el análisis de riesgos)."),
                ("Elección del modelo",
                 "Depende de la estabilidad de los requisitos, el tamaño del equipo, el riesgo técnico y la necesidad "
                 "de entregar valor pronto."),
            ],
            "ejemplo": {
                "enunciado": "Elija el modelo de ciclo de vida para un sistema de matrícula cuyos requisitos legales "
                             "están definidos, pero cuya interfaz se validará con estudiantes.",
                "pasos": [
                    "Identificar lo estable: reglas de matrícula y normativa (bien definidas).",
                    "Identificar lo incierto: la interfaz y la experiencia del estudiante.",
                    "Descartar cascada pura: no permite validar la interfaz antes del final.",
                    "Proponer un modelo incremental: incremento 1 con reglas y registro; incremento 2 con la interfaz "
                    "validada con usuarios.",
                ],
                "resultado": "Modelo incremental: entrega temprana de lo estable y validación progresiva de lo incierto.",
            },
            "ejercicios": [
                "Compare cascada, incremental y espiral en una tabla (planificación, riesgo, entregas).",
                "Proponga el modelo para una app de turnos médicos con requisitos cambiantes y justifíquelo.",
                "Describa las 4 actividades del proceso de software aplicadas a su proyecto de aula.",
            ],
        },
        2: {
            "titulo": "Ingeniería de requisitos",
            "temas": [
                ("Requisitos funcionales y no funcionales",
                 "Los funcionales describen lo que el sistema hace (registrar una nota); los no funcionales, cómo lo "
                 "hace (tiempo de respuesta, seguridad, disponibilidad)."),
                ("Técnicas de obtención",
                 "Entrevistas, cuestionarios, observación, talleres y prototipos permiten descubrir necesidades reales "
                 "de los usuarios."),
                ("Especificación verificable",
                 "Un buen requisito es claro, medible y comprobable: evita palabras ambiguas como «rápido» o «fácil»."),
            ],
            "ejemplo": {
                "enunciado": "Reescriba de forma verificable el requisito: 'El sistema debe ser rápido al buscar "
                             "estudiantes'.",
                "pasos": [
                    "Detectar la ambigüedad: «rápido» no se puede medir.",
                    "Clasificarlo: es un requisito no funcional de rendimiento.",
                    "Definir la métrica: tiempo de respuesta de la búsqueda.",
                    "Fijar condiciones: con 5 000 estudiantes registrados y 50 usuarios simultáneos.",
                ],
                "resultado": "RNF-01: la búsqueda de un estudiante por cédula responde en menos de 2 segundos con 5 000 "
                             "registros y 50 usuarios simultáneos.",
            },
            "ejercicios": [
                "Escriba 3 requisitos funcionales y 2 no funcionales para un sistema de biblioteca.",
                "Reescriba de forma verificable: 'La aplicación debe ser segura y fácil de usar'.",
                "Prepare 5 preguntas de entrevista para obtener requisitos de un docente.",
            ],
        },
        3: {
            "titulo": "Modelado del sistema con UML",
            "temas": [
                ("Casos de uso",
                 "Representan cómo los actores interactúan con el sistema para lograr un objetivo; se relacionan con "
                 "«include» (obligatorio) y «extend» (opcional)."),
                ("Diagrama de clases",
                 "Muestra las clases, sus atributos, métodos y relaciones (asociación, agregación, composición y "
                 "herencia) con su multiplicidad."),
                ("Diagrama de secuencia",
                 "Describe el orden de los mensajes entre objetos para un escenario concreto de un caso de uso."),
            ],
            "ejemplo": {
                "enunciado": "Modele las clases principales de 'Un docente dicta varios cursos y cada curso tiene "
                             "muchos estudiantes matriculados'.",
                "pasos": [
                    "Identificar sustantivos: Docente, Curso, Estudiante, Matrícula.",
                    "Docente 1 - 0..* Curso: un docente dicta varios cursos.",
                    "Curso 1 - 0..* Matrícula y Estudiante 1 - 0..* Matrícula (clase asociativa).",
                    "Agregar atributos clave: cédula, nombres (Estudiante); código, paralelo (Curso); fecha (Matrícula).",
                ],
                "resultado": "Cuatro clases con multiplicidades que permiten consultar los cursos de un docente y la "
                             "nómina de cada curso.",
            },
            "ejercicios": [
                "Dibuje el diagrama de casos de uso de un cajero automático con 3 actores.",
                "Agregue la clase Calificación al modelo del ejemplo e indique sus relaciones.",
                "Elabore el diagrama de secuencia del caso «Registrar matrícula».",
            ],
        },
        4: {
            "titulo": "Diseño arquitectónico y pruebas",
            "temas": [
                ("Arquitectura en capas",
                 "Separa presentación, lógica de negocio y datos; cada capa usa sólo la inferior, lo que facilita el "
                 "mantenimiento y las pruebas."),
                ("Cliente-servidor y microservicios",
                 "En cliente-servidor varios clientes consumen un servidor central; en microservicios, servicios "
                 "pequeños e independientes se comunican por API."),
                ("Pruebas de software",
                 "Unitarias (una función), de integración (componentes juntos) y de aceptación (el usuario valida "
                 "que el sistema cumple sus requisitos)."),
            ],
            "ejemplo": {
                "enunciado": "Diseñe casos de prueba para la función calcularPromedio(notas) que debe rechazar notas "
                             "fuera de 0 a 10.",
                "pasos": [
                    "Caso válido: [8, 6, 10] => 8.00.",
                    "Valores límite: [0, 10] => 5.00.",
                    "Caso inválido: [11, 7] => error 'nota fuera de rango'.",
                    "Lista vacía: [] => error 'sin notas'.",
                ],
                "resultado": "Cuatro casos cubren el escenario normal, los límites y los errores esperados.",
            },
            "ejercicios": [
                "Represente en capas un sistema de matrícula indicando qué hace cada capa.",
                "Escriba 4 casos de prueba para una función que valida cédulas de 10 dígitos.",
                "Explique cuándo conviene microservicios en lugar de una aplicación monolítica.",
            ],
        },
    },
    # ------------------------------------------------------------------ Bases de Datos Avanzadas
    "BDA": {
        1: {
            "titulo": "Modelo relacional y normalización",
            "temas": [
                ("Modelo relacional",
                 "Organiza los datos en tablas con claves primarias que identifican cada fila y claves foráneas que "
                 "relacionan tablas entre sí."),
                ("Dependencias funcionales",
                 "A determina a B cuando cada valor de A corresponde a un único valor de B (la cédula determina el "
                 "nombre del estudiante)."),
                ("Formas normales",
                 "1FN: valores atómicos; 2FN: sin dependencias parciales de la clave; 3FN: sin dependencias "
                 "transitivas entre atributos no clave."),
            ],
            "ejemplo": {
                "enunciado": "Normalice a 3FN la tabla Matricula(cedula, nombre, codigo_curso, nombre_curso, docente).",
                "pasos": [
                    "Clave primaria: (cedula, codigo_curso).",
                    "Dependencia parcial: cedula => nombre. Se crea Estudiante(cedula, nombre).",
                    "Dependencia parcial: codigo_curso => nombre_curso, docente. Se crea Curso(codigo_curso, "
                    "nombre_curso, docente).",
                    "Queda Matricula(cedula, codigo_curso) con claves foráneas a Estudiante y Curso.",
                ],
                "resultado": "Tres tablas en 3FN sin redundancia: cambiar el docente de un curso afecta a una sola fila.",
            },
            "ejercicios": [
                "Indique las dependencias funcionales de Factura(numero, fecha, cedula_cliente, nombre_cliente, total).",
                "Normalice a 3FN la tabla del ejercicio anterior.",
                "Explique con un ejemplo qué anomalía de actualización evita la normalización.",
            ],
        },
        2: {
            "titulo": "SQL avanzado: consultas, vistas y procedimientos",
            "temas": [
                ("Combinaciones (JOIN)",
                 "INNER JOIN devuelve sólo las filas que coinciden en ambas tablas; LEFT JOIN conserva todas las filas "
                 "de la tabla izquierda aunque no tengan pareja."),
                ("Agrupación y subconsultas",
                 "GROUP BY con funciones de agregado (AVG, COUNT) resume datos; HAVING filtra los grupos; una "
                 "subconsulta usa el resultado de otra consulta."),
                ("Vistas y procedimientos almacenados",
                 "Una vista guarda una consulta reutilizable; un procedimiento almacenado encapsula lógica con "
                 "parámetros dentro del motor de base de datos."),
            ],
            "ejemplo": {
                "enunciado": "Obtenga los cursos cuyo promedio de notas es menor a 7.",
                "pasos": [
                    "Unir notas con cursos: 'FROM nota n JOIN curso c ON c.id = n.curso_id'.",
                    "Agrupar por curso: 'GROUP BY c.codigo'.",
                    "Calcular el promedio: 'SELECT c.codigo, AVG(n.valor) AS promedio'.",
                    "Filtrar los grupos: 'HAVING AVG(n.valor) < 7'.",
                ],
                "resultado": "La consulta devuelve sólo los cursos con promedio inferior a 7, con su promedio calculado.",
            },
            "ejercicios": [
                "Liste los estudiantes sin ninguna nota registrada usando LEFT JOIN.",
                "Cree una vista con el promedio de cada estudiante por curso.",
                "Escriba un procedimiento almacenado que reciba una cédula y devuelva sus notas.",
            ],
        },
        3: {
            "titulo": "Transacciones y control de concurrencia",
            "temas": [
                ("Propiedades ACID",
                 "Atomicidad (todo o nada), consistencia (reglas válidas), aislamiento (transacciones independientes) "
                 "y durabilidad (lo confirmado persiste)."),
                ("COMMIT y ROLLBACK",
                 "COMMIT confirma los cambios de la transacción; ROLLBACK los deshace si ocurre un error."),
                ("Niveles de aislamiento",
                 "READ COMMITTED evita lecturas sucias; REPEATABLE READ evita lecturas no repetibles; SERIALIZABLE "
                 "evita también los registros fantasma, con más bloqueos."),
            ],
            "ejemplo": {
                "enunciado": "Transfiera 100 dólares de la cuenta A a la cuenta B sin dejar datos inconsistentes.",
                "pasos": [
                    "Iniciar: 'BEGIN TRANSACTION'.",
                    "Debitar la cuenta A (id 1): 'UPDATE cuenta SET saldo = saldo - 100 WHERE id = 1'.",
                    "Acreditar la cuenta B (id 2): 'UPDATE cuenta SET saldo = saldo + 100 WHERE id = 2'.",
                    "Si ambas operaciones tienen éxito: 'COMMIT'; si alguna falla: 'ROLLBACK'.",
                ],
                "resultado": "El dinero nunca desaparece: o se aplican ambos cambios o ninguno (atomicidad).",
            },
            "ejercicios": [
                "Explique con un ejemplo de matrícula qué es una lectura sucia.",
                "Escriba la transacción que registra una matrícula y descuenta un cupo del curso.",
                "Compare READ COMMITTED y SERIALIZABLE en seguridad y rendimiento.",
            ],
        },
        4: {
            "titulo": "Índices y optimización de consultas",
            "temas": [
                ("Índices",
                 "Estructuras (normalmente árboles B) que aceleran las búsquedas por una columna, a cambio de espacio "
                 "y de escrituras algo más lentas."),
                ("Plan de ejecución",
                 "Muestra cómo el motor resuelve la consulta: un recorrido completo de la tabla (scan) o una búsqueda "
                 "en un índice (seek)."),
                ("Buenas prácticas",
                 "Indexar columnas de filtros y JOIN, evitar funciones sobre columnas indexadas y seleccionar sólo las "
                 "columnas necesarias."),
            ],
            "ejemplo": {
                "enunciado": "La consulta 'SELECT * FROM estudiante WHERE cedula = :cedula' tarda varios segundos.",
                "pasos": [
                    "Revisar el plan de ejecución: aparece un recorrido completo de la tabla (table scan).",
                    "Crear el índice: 'CREATE INDEX ix_estudiante_cedula ON estudiante(cedula)'.",
                    "Seleccionar sólo lo necesario: 'SELECT cedula, nombres FROM estudiante WHERE cedula = ...'.",
                    "Volver a revisar el plan: ahora usa una búsqueda en el índice (index seek).",
                ],
                "resultado": "La búsqueda pasa de recorrer toda la tabla a localizar la fila directamente en el índice.",
            },
            "ejercicios": [
                "Indique qué columnas indexaría en una tabla de notas consultada por estudiante y curso.",
                "Explique por qué 'WHERE YEAR(fecha) = 2026' puede no usar un índice sobre fecha.",
                "Compare un table scan y un index seek con un ejemplo de 100 000 filas.",
            ],
        },
    },
    # ------------------------------------------------------------------ Desarrollo Web
    "DW": {
        1: {
            "titulo": "Fundamentos de la web: HTML y CSS",
            "temas": [
                ("Estructura semántica con HTML",
                 "Etiquetas como header, nav, main, section y footer describen el significado del contenido y mejoran "
                 "la accesibilidad y el posicionamiento."),
                ("Estilos con CSS",
                 "Los selectores aplican reglas de estilo; la especificidad decide qué regla gana cuando varias "
                 "afectan al mismo elemento."),
                ("Diseño adaptable",
                 "Flexbox y Grid organizan el contenido; las media queries adaptan el diseño al ancho de la pantalla."),
            ],
            "ejemplo": {
                "enunciado": "Construya una tarjeta de curso que muestre dos columnas en escritorio y una en el celular.",
                "pasos": [
                    "HTML: un contenedor 'div class=\"cursos\"' con varios 'article class=\"tarjeta\"'.",
                    "CSS base: '.cursos { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }'.",
                    "Media query: '@media (max-width: 600px) { .cursos { grid-template-columns: 1fr; } }'.",
                    "Probar reduciendo el ancho del navegador por debajo de 600 px.",
                ],
                "resultado": "Las tarjetas se muestran en 2 columnas en escritorio y en 1 columna en pantallas pequeñas.",
            },
            "ejercicios": [
                "Maquete con etiquetas semánticas la página principal de una biblioteca virtual.",
                "Calcule qué regla gana entre '#menu a' y '.nav a' y explique por qué.",
                "Cree con Flexbox una barra de navegación que se apile en pantallas pequeñas.",
            ],
        },
        2: {
            "titulo": "JavaScript y manipulación del DOM",
            "temas": [
                ("Variables y funciones",
                 "let y const declaran variables con alcance de bloque; las funciones flecha simplifican la escritura "
                 "de funciones cortas."),
                ("El DOM",
                 "Es la representación del documento como árbol de nodos: con querySelector se seleccionan elementos "
                 "y se modifican su texto, clases o atributos."),
                ("Eventos",
                 "addEventListener ejecuta una función cuando ocurre una acción del usuario (click, input, submit)."),
            ],
            "ejemplo": {
                "enunciado": "Muestre en pantalla el promedio de tres notas al pulsar un botón 'Calcular'.",
                "pasos": [
                    "Seleccionar el botón: 'const boton = document.querySelector('#calcular')'.",
                    "Escuchar el clic: 'boton.addEventListener('click', calcular)'.",
                    "Leer las notas: '[...document.querySelectorAll('.nota')].map(n => Number(n.value))'.",
                    "Mostrar el resultado: 'salida.textContent = (suma / 3).toFixed(2)'.",
                ],
                "resultado": "Con notas 8, 6 y 10 la página muestra 8.00 sin recargarse.",
            },
            "ejercicios": [
                "Valide que un campo de correo termine en '@uta.edu.ec' antes de enviar el formulario.",
                "Agregue y elimine elementos de una lista de tareas usando el DOM.",
                "Explique la diferencia entre let, const y var con un ejemplo.",
            ],
        },
        3: {
            "titulo": "Backend y API REST",
            "temas": [
                ("Arquitectura cliente-servidor en la web",
                 "El navegador (cliente) envía peticiones HTTP; el servidor procesa la lógica, consulta la base de "
                 "datos y responde, normalmente en JSON."),
                ("Diseño de API REST",
                 "Los recursos se identifican con URL (/estudiantes/15) y los verbos HTTP indican la acción: GET "
                 "consulta, POST crea, PUT actualiza y DELETE elimina."),
                ("Códigos de estado",
                 "200 éxito, 201 creado, 400 petición inválida, 401 no autenticado, 404 no encontrado y 500 error del "
                 "servidor."),
            ],
            "ejemplo": {
                "enunciado": "Diseñe los endpoints para gestionar las notas de un curso.",
                "pasos": [
                    "Listar las notas del curso: 'GET /cursos/{id}/notas' => 200 con la lista.",
                    "Registrar una nota: 'POST /cursos/{id}/notas' con el JSON de la nota => 201.",
                    "Corregir una nota: 'PUT /notas/{id}' => 200; si no existe => 404.",
                    "Validar el rango: una nota fuera de 0 a 10 responde 400 con el mensaje de error.",
                ],
                "resultado": "Cuatro endpoints coherentes con los verbos HTTP y códigos de estado claros.",
            },
            "ejercicios": [
                "Diseñe los endpoints REST para gestionar estudiantes (listar, crear, editar, eliminar).",
                "Indique el código de estado correcto cuando se pide una nota que no existe.",
                "Escriba el JSON de respuesta de 'GET /estudiantes/15'.",
            ],
        },
        4: {
            "titulo": "Frameworks, seguridad y despliegue",
            "temas": [
                ("Frameworks de interfaz",
                 "React, Angular o Vue organizan la interfaz en componentes reutilizables que se actualizan "
                 "automáticamente cuando cambia su estado."),
                ("Seguridad web",
                 "Validar siempre en el servidor, usar consultas parametrizadas contra la inyección SQL, escapar la "
                 "salida contra XSS y servir el sitio con HTTPS."),
                ("Despliegue",
                 "Se compila la aplicación, se configuran variables de entorno (nunca contraseñas en el código) y se "
                 "publica en un servidor o contenedor."),
            ],
            "ejemplo": {
                "enunciado": "Corrija una consulta vulnerable que concatena el correo escrito por el usuario dentro "
                             "del texto SQL.",
                "pasos": [
                    "Identificar el riesgo: un texto como 'x OR 1 = 1' cambia el sentido de la consulta (inyección SQL).",
                    "Usar un parámetro: 'SELECT * FROM usuario WHERE correo = ?'.",
                    "Enviar el valor por separado: 'cursor.execute(sql, (correo,))'.",
                    "Validar además el formato del correo en el servidor antes de consultar.",
                ],
                "resultado": "El motor trata el correo sólo como dato, por lo que el ataque deja de funcionar.",
            },
            "ejercicios": [
                "Divida en componentes la pantalla de un listado de cursos con buscador.",
                "Explique cómo evitar XSS al mostrar comentarios de usuarios en una página.",
                "Liste los pasos para desplegar una aplicación web usando variables de entorno.",
            ],
        },
    },
}


def sigla_curso(shortname: str) -> str:
    """'SOF-POO-A' => 'POO'."""
    partes = [p for p in (shortname or "").upper().split("-") if p and p != "SOF"]
    return partes[0] if partes else (shortname or "").upper()


def contenido_unidad(shortname: str, unidad: int) -> Optional[Unidad]:
    """Contenido de la materia y unidad; None si la materia no está en el catálogo."""
    materia = CONTENIDOS.get(sigla_curso(shortname))
    if not materia:
        return None
    return materia.get(unidad) or materia.get(min(materia, key=lambda u: abs(u - unidad)))
