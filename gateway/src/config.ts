import "dotenv/config";

import { z } from "zod";

const environmentSchema = z.enum(["development", "test", "production"]);
const plainOriginSchema = z.string().url().refine((value) => {
  const parsed = new URL(value);
  return (
    ["http:", "https:"].includes(parsed.protocol) &&
    parsed.username === "" &&
    parsed.password === "" &&
    (parsed.pathname === "/" || parsed.pathname === "") &&
    parsed.search === "" &&
    parsed.hash === ""
  );
}, "Expected a plain HTTP(S) origin without credentials or a path");

const configSchema = z.object({
  AI_SERVICE_URL: plainOriginSchema.default("http://127.0.0.1:8000"),
  APP_VERSION: z.string().min(1).default("0.15.0"),
  FRONTEND_ORIGIN: plainOriginSchema.default("http://localhost:5173"),
  GATEWAY_RATE_LIMIT_MAX: z.coerce.number().int().positive().max(1_000).default(30),
  GATEWAY_RATE_LIMIT_WINDOW_MS: z.coerce.number().int().positive().max(3_600_000).default(60_000),
  GATEWAY_UPSTREAM_TIMEOUT_MS: z.coerce.number().int().positive().max(600_000).default(130_000),
  NODE_ENV: environmentSchema.default("development"),
  PORT: z.coerce.number().int().positive().max(65_535).default(4000),
}).superRefine((value, context) => {
  if (value.NODE_ENV === "production" && !value.AI_SERVICE_URL.startsWith("https://")) {
    context.addIssue({ code: z.ZodIssueCode.custom, message: "Production AI_SERVICE_URL must use HTTPS", path: ["AI_SERVICE_URL"] });
  }
  if (value.NODE_ENV === "production" && !value.FRONTEND_ORIGIN.startsWith("https://")) {
    context.addIssue({ code: z.ZodIssueCode.custom, message: "Production FRONTEND_ORIGIN must use HTTPS", path: ["FRONTEND_ORIGIN"] });
  }
});

export type Environment = z.infer<typeof environmentSchema>;

export interface GatewayConfig {
  aiServiceUrl: string;
  corsOrigin: string;
  environment: Environment;
  port: number;
  rateLimitMax: number;
  rateLimitWindowMs: number;
  upstreamTimeoutMs: number;
  version: string;
}

export function loadConfig(source: NodeJS.ProcessEnv): GatewayConfig {
  const parsed = configSchema.parse({
    ...source,
    // CORS_ORIGIN remains a local backwards-compatible alias. New deployments use
    // the explicit FRONTEND_ORIGIN name documented by the deployment contract.
    FRONTEND_ORIGIN: source.FRONTEND_ORIGIN ?? source.CORS_ORIGIN,
  });

  return {
    aiServiceUrl: parsed.AI_SERVICE_URL.replace(/\/$/, ""),
    corsOrigin: parsed.FRONTEND_ORIGIN.replace(/\/$/, ""),
    environment: parsed.NODE_ENV,
    port: parsed.PORT,
    rateLimitMax: parsed.GATEWAY_RATE_LIMIT_MAX,
    rateLimitWindowMs: parsed.GATEWAY_RATE_LIMIT_WINDOW_MS,
    upstreamTimeoutMs: parsed.GATEWAY_UPSTREAM_TIMEOUT_MS,
    version: parsed.APP_VERSION,
  };
}
