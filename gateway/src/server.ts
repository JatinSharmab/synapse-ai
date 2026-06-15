import { createApp } from "./app.js";
import { loadConfig } from "./config.js";

const config = loadConfig(process.env);
const app = createApp(config);

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

