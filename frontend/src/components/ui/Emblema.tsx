/**
 * Emblema minimalista institucional UTA · FISEI (escudo azul marino con filete dorado).
 * Colores: #0B2A5B (azul institucional) y #C59B27 (dorado).
 * Es un emblema propio y simplificado del proyecto, no el escudo oficial de la universidad.
 */
export function Emblema({ tamano = 56, titulo = 'Emblema UTA · FISEI' }: { tamano?: number; titulo?: string }) {
  return (
    <svg
      width={tamano}
      height={Math.round(tamano * 1.125)}
      viewBox="0 0 64 72"
      role="img"
      aria-label={titulo}
      className="emblema"
    >
      <title>{titulo}</title>
      <path d="M32 2 L60 10 V34 C60 52 47.5 63.5 32 70 C16.5 63.5 4 52 4 34 V10 Z" fill="#0B2A5B" stroke="#C59B27" strokeWidth="3" />
      <path d="M32 9 L53 15 V34 C53 47.5 44 56.5 32 62 C20 56.5 11 47.5 11 34 V15 Z" fill="none" stroke="#C59B27" strokeOpacity="0.45" strokeWidth="1" />
      <path d="M20 20 L32 16 L44 20" fill="none" stroke="#C59B27" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <text x="32" y="38" textAnchor="middle" fontFamily="Georgia, 'Times New Roman', serif" fontSize="15" fontWeight="700" fill="#FFFFFF" letterSpacing="1">
        UTA
      </text>
      <line x1="21" y1="43" x2="43" y2="43" stroke="#C59B27" strokeWidth="1.2" />
      <text x="32" y="52" textAnchor="middle" fontFamily="Arial, Helvetica, sans-serif" fontSize="6.5" fontWeight="700" fill="#C59B27" letterSpacing="1.2">
        FISEI
      </text>
    </svg>
  );
}
