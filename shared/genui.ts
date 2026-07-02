import { z } from "zod";

const keyPattern = /^[A-Za-z][A-Za-z0-9_]{0,63}$/;
const unsafeMarkupPattern = /<\s*\/?\s*[a-z!][^>]*>|javascript\s*:|\bon[a-z]+\s*=/i;

const safeString = (maximum: number) =>
  z
    .string()
    .trim()
    .min(1)
    .max(maximum)
    .refine((value) => !unsafeMarkupPattern.test(value), {
      message: "HTML, scripts, and event handlers are not allowed in Gen-UI",
    });

const identifierSchema = z.string().regex(keyPattern);
const valueSchema = z.union([
  safeString(2_000),
  z.number().finite(),
  z.boolean(),
  z.null(),
]);
const dataRowSchema = z
  .record(valueSchema)
  .refine((row) => Object.keys(row).length <= 20, "Gen-UI rows may contain at most 20 fields")
  .refine(
    (row) => Object.keys(row).every((key) => keyPattern.test(key)),
    "Gen-UI data keys must be safe identifiers",
  );

const commonShape = {
  version: z.literal("1.0"),
  title: safeString(200).optional(),
};

const textComponentSchema = z
  .object({
    ...commonShape,
    type: z.literal("text"),
    text: safeString(2_000),
  })
  .strict();

const metricComponentSchema = z
  .object({
    ...commonShape,
    type: z.literal("metric"),
    label: safeString(120),
    value: z.union([safeString(2_000), z.number().finite()]),
    unit: safeString(32).optional(),
  })
  .strict();

const xyConfigSchema = z
  .object({
    xKey: identifierSchema,
    yKey: identifierSchema,
  })
  .strict();

const pieConfigSchema = z
  .object({
    labelKey: identifierSchema,
    valueKey: identifierSchema,
  })
  .strict();

const barChartComponentSchema = z
  .object({
    ...commonShape,
    type: z.literal("bar_chart"),
    title: safeString(200),
    data: z.array(dataRowSchema).min(1).max(100),
    config: xyConfigSchema,
  })
  .strict();

const lineChartComponentSchema = z
  .object({
    ...commonShape,
    type: z.literal("line_chart"),
    title: safeString(200),
    data: z.array(dataRowSchema).min(2).max(100),
    config: xyConfigSchema,
  })
  .strict();

const pieChartComponentSchema = z
  .object({
    ...commonShape,
    type: z.literal("pie_chart"),
    title: safeString(200),
    data: z.array(dataRowSchema).min(1).max(30),
    config: pieConfigSchema,
  })
  .strict();

const tableColumnSchema = z
  .object({
    key: identifierSchema,
    label: safeString(120),
  })
  .strict();

const tableComponentSchema = z
  .object({
    ...commonShape,
    type: z.literal("table"),
    title: safeString(200),
    columns: z.array(tableColumnSchema).min(1).max(20),
    data: z.array(dataRowSchema).max(100),
  })
  .strict();

const citationItemSchema = z
  .object({
    citation_id: safeString(128),
    label: safeString(300),
    locator: safeString(300),
    source_type: z.enum(["document", "video"]),
  })
  .strict();

const citationListComponentSchema = z
  .object({
    ...commonShape,
    type: z.literal("citation_list"),
    title: safeString(200).default("Sources"),
    citations: z.array(citationItemSchema).min(1).max(20),
  })
  .strict();

const videoEvidenceItemSchema = z
  .object({
    video_id: safeString(128),
    filename: safeString(255),
    segment_id: safeString(128),
    start_seconds: z.number().finite().nonnegative(),
    end_seconds: z.number().finite().positive(),
    description: safeString(1_000),
  })
  .strict()
  .refine((item) => item.end_seconds > item.start_seconds, {
    message: "Video evidence end_seconds must be greater than start_seconds",
  });

const videoEvidenceComponentSchema = z
  .object({
    ...commonShape,
    type: z.literal("video_evidence"),
    title: safeString(200).default("Video evidence"),
    items: z.array(videoEvidenceItemSchema).min(1).max(20),
  })
  .strict();

const rawGenUIComponentSchema = z.discriminatedUnion("type", [
  textComponentSchema,
  metricComponentSchema,
  barChartComponentSchema,
  lineChartComponentSchema,
  pieChartComponentSchema,
  tableComponentSchema,
  citationListComponentSchema,
  videoEvidenceComponentSchema,
]);

export const genUIComponentSchema = rawGenUIComponentSchema.superRefine((component, context) => {
  if (
    component.type === "bar_chart" ||
    component.type === "line_chart" ||
    component.type === "pie_chart"
  ) {
    const labelKey = component.type === "pie_chart" ? component.config.labelKey : component.config.xKey;
    const numericKey = component.type === "pie_chart" ? component.config.valueKey : component.config.yKey;
    if (labelKey === numericKey) {
      context.addIssue({ code: z.ZodIssueCode.custom, message: "Chart keys must differ" });
    }
    component.data.forEach((row, index) => {
      if (!(labelKey in row) || !(numericKey in row)) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          message: "Every chart row must contain the configured keys",
          path: ["data", index],
        });
      } else if (typeof row[numericKey] !== "number") {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          message: "Chart numeric keys must reference finite numbers",
          path: ["data", index, numericKey],
        });
      }
    });
  }
  if (component.type === "table") {
    const keys = component.columns.map((column) => column.key);
    if (new Set(keys).size !== keys.length) {
      context.addIssue({ code: z.ZodIssueCode.custom, message: "Table column keys must be unique" });
    }
    component.data.forEach((row, index) => {
      if (keys.some((key) => !(key in row))) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          message: "Every table row must contain every configured key",
          path: ["data", index],
        });
      }
    });
  }
});

export const genUIResponseSchema = z
  .object({
    components: z.array(genUIComponentSchema).max(5),
  })
  .strict();

export type GenUIComponent = z.infer<typeof genUIComponentSchema>;
export type GenUIResponse = z.infer<typeof genUIResponseSchema>;
export type GenUIType = GenUIComponent["type"];
