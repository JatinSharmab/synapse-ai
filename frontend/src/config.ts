const DEFAULT_GATEWAY_URL = "http://localhost:4000";
const DEFAULT_LOCAL_AI_URL = "/ai-local";
const gatewayUrl = import.meta.env.VITE_GATEWAY_URL || DEFAULT_GATEWAY_URL;

export const runtimeConfig = {
  gatewayUrl,
  // Browser control requests go through the deployed gateway. The direct AI
  // URL remains a development-only Vite proxy and never enters a production bundle.
  aiServiceUrl: import.meta.env.PROD
    ? gatewayUrl
    : import.meta.env.VITE_AI_SERVICE_URL || DEFAULT_LOCAL_AI_URL,
  directUploadsEnabled:
    import.meta.env.DEV && import.meta.env.VITE_ENABLE_LOCAL_UPLOADS !== "false",
} as const;
