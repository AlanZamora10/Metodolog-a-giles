/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** URL pública de Moodle UTA, p. ej. http://localhost:8080 */
  readonly VITE_MOODLE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
