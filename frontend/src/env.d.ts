/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_DEMO_VK_ID?: string;
  readonly VITE_BETA_VK_IDS?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
