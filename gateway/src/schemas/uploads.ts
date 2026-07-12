import { z } from "zod";

function hasControlCharacter(value: string): boolean {
  return [...value].some((character) => {
    const codePoint = character.codePointAt(0) ?? 0;
    return codePoint <= 31
      || (codePoint >= 127 && codePoint <= 159)
      || /\p{Cf}/u.test(character);
  });
}

const safeFilenameSchema = z.string().min(1).max(255)
  .refine((value) => value.trim() === value, "Filename must not have surrounding whitespace")
  .refine((value) => !value.includes("/") && !value.includes("\\"), "Filename must not contain a path")
  .refine((value) => !hasControlCharacter(value) && value !== "." && value !== "..", "Filename contains unsafe characters");

export const presignUploadRequestSchema = z.object({
  asset_type: z.enum(["document", "video"]),
  content_type: z.string().min(1).max(100),
  filename: safeFilenameSchema,
  size_bytes: z.number().int().positive().max(100 * 1024 * 1024),
}).strict().superRefine((value, context) => {
  const validDocument = value.asset_type === "document" && value.filename.toLowerCase().endsWith(".pdf") && value.content_type === "application/pdf";
  const validVideo = value.asset_type === "video" && value.filename.toLowerCase().endsWith(".mp4") && ["video/mp4", "application/mp4"].includes(value.content_type);
  if (!validDocument && !validVideo) {
    context.addIssue({ code: z.ZodIssueCode.custom, message: "Filename and MIME type do not match the asset type" });
  }
});

export const storedObjectRequestSchema = z.object({
  object_path: z.string().min(1).max(400).refine((value) => {
    const parts = value.split("/");
    return parts.length === 3
      && (parts[0] === "documents" || parts[0] === "videos")
      && /^[a-f0-9]{32}$/.test(parts[1] ?? "")
      && safeFilenameSchema.safeParse(parts[2]).success;
  }, "Object path is invalid"),
}).strict();
