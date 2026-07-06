import { z } from "zod";

export const chatStreamRequestSchema = z
  .object({
    message: z.string().trim().min(1).max(4_000),
    thread_id: z.string().trim().min(1).max(128).regex(/^[A-Za-z0-9._:-]+$/),
  })
  .strict();

export type ChatStreamRequest = z.infer<typeof chatStreamRequestSchema>;
