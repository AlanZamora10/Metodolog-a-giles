Fondo opcional del login de Moodle UTA (http://localhost:8080/login/index.php)

1. Pegue aqui una imagen llamada login-bg.jpg (tambien sirve login-bg.png, .jpeg o .webp).
2. Aplique el tema sin re-sembrar datos:
     docker exec moodle_lms bash /opt/edumonitor_seed/entrypoint-seed.sh --tema-only
   (tambien se aplica solo en cada reinicio del contenedor moodle_lms).

La imagen se muestra completa, centrada y nitida (sin velos ni filtros); las bandas libres se
rellenan con el color del borde de la imagen y la tarjeta institucional blanca queda centrada. Si borra la imagen y vuelve a aplicar el tema, el login recupera su fondo actual.
Recomendado: 1920x1080 o mayor, menos de 500 KB.
