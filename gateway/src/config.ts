import "dotenv/config";

import { z } from "zod";

const environmentSchema = z.enum(["development", "test", "production"]);

const configSchema = z.object({
  APP_VERSION: z.string().min(1).default("0.1.0"),
  CORS_ORIGIN: z.string().min(1).default("http://localhost:5173"),
  NODE_ENV: environmentSchema.default("development"),
  PORT: z.coerce.number().int().positive().max(65_535).default(4000),
});

export type Environment = z.infer<typeof environmentSchema>;

export interface GatewayConfig {
  corsOrigin: string;
  environment: Environment;
  port: number;
  version: string;
}

export function loadConfig(source: NodeJS.ProcessEnv): GatewayConfig {
  const parsed = configSchema.parse(source);

  return {
    corsOrigin: parsed.CORS_ORIGIN,
    environment: parsed.NODE_ENV,
    port: parsed.PORT,
    version: parsed.APP_VERSION,
  };
}

