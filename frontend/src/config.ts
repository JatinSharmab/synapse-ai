const DEFAULT_GATEWAY_URL = "http://localhost:4000";

export const runtimeConfig = {
  gatewayUrl: import.meta.env.VITE_GATEWAY_URL || DEFAULT_GATEWAY_URL,
} as const;

