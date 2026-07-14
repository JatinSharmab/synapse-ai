import { createApp } from "./app.js";
import { loadConfig } from "./config.js";

// Vercel discovers this default Express export. The local server imports the
// same instance and owns listen(), keeping transport behavior identical.
const app = createApp(loadConfig(process.env));

export default app;
