import app from "./index.js";
import { loadConfig } from "./config.js";

const config = loadConfig(process.env);

app.listen(config.port, () => {
  console.info(
    JSON.stringify({
      event: "gateway.started",
      environment: config.environment,
      port: config.port,
      service: "synapse-gateway",
      version: config.version,
    }),
  );
});
