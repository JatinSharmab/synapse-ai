import { z } from "zod";

export const healthResponseSchema = z.object({
  service: z.literal("synapse-gateway"),
  status: z.literal("ok"),
  version: z.string().min(1),
  environment: z.enum(["development", "test", "production"]),
});

export type HealthResponse = z.infer<typeof healthResponseSchema>;

