export {};

declare global {
  interface Window {
    __APP_CONFIG__?: {
      VITE_API_BASE_URL?: string;
    };
  }
}
