import cors from "cors";
import express, { type Express } from "express";
import helmet from "helmet";
import morgan from "morgan";

import type { Environment } from "./config.js";
import { healthResponseSchema } from "./schemas/health.js";

export interface GatewayRuntime {
  corsOrigin: string;
  environment: Environment;
  version: string;
}

export function createApp(runtime: GatewayRuntime): Express {
  const app = express();

  app.disable("x-powered-by");
  app.use(helmet());
  app.use(cors({ origin: runtime.corsOrigin }));

  if (runtime.environment !== "test") {
    app.use(morgan("combined"));
  }

  app.get("/health", (_request, response) => {
    const health = healthResponseSchema.parse({
      service: "synapse-gateway",
      status: "ok",
      version: runtime.version,
      environment: runtime.environment,
    });

    response.status(200).json(health);
  });

  return app;
}

