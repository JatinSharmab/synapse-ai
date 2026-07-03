import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, it } from "node:test";

import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { GenUIRenderer, componentRegistry } from "../src/genui/renderer.js";
import { genUIComponentSchema } from "../src/genui/schema.js";

const validChart = {
  version: "1.0",
  type: "bar_chart",
  title: "Revenue by Region",
  data: [
    { region: "North", revenue: 120 },
    { region: "South", revenue: 95 },
  ],
  config: { xKey: "region", yKey: "revenue" },
};

describe("Gen-UI Zod protocol", () => {
  it("accepts a valid chart payload", () => {
    assert.equal(genUIComponentSchema.safeParse(validChart).success, true);
  });

  it("rejects invalid and unknown component types", () => {
    assert.equal(
      genUIComponentSchema.safeParse({ ...validChart, type: "dashboard" }).success,
      false,
    );
    assert.equal(
      genUIComponentSchema.safeParse({ ...validChart, type: "custom_widget" }).success,
      false,
    );
  });

  it("rejects missing fields and malformed chart data", () => {
    const missingConfig = {
      version: validChart.version,
      type: validChart.type,
      title: validChart.title,
      data: validChart.data,
    };
    assert.equal(genUIComponentSchema.safeParse(missingConfig).success, false);
    assert.equal(
      genUIComponentSchema.safeParse({
        ...validChart,
        data: [{ region: "North", revenue: "not-a-number" }],
      }).success,
      false,
    );
  });

  it("rejects HTML, scripts, and event-handler attempts", () => {
    for (const text of ["<script>alert(1)</script>", "<img src=x onerror=alert(1)>", "javascript:alert(1)"]) {
      assert.equal(
        genUIComponentSchema.safeParse({ version: "1.0", type: "text", text }).success,
        false,
      );
    }
  });

  it("rejects unknown fields and invalid chart keys", () => {
    assert.equal(
      genUIComponentSchema.safeParse({ ...validChart, component: "ArbitraryReact" }).success,
      false,
    );
    assert.equal(
      genUIComponentSchema.safeParse({
        ...validChart,
        config: { xKey: "missing", yKey: "revenue" },
      }).success,
      false,
    );
    assert.equal(
      genUIComponentSchema.safeParse({
        ...validChart,
        config: { xKey: "region", yKey: "region" },
      }).success,
      false,
    );
  });
});

describe("fixed Gen-UI renderer", () => {
  it("contains exactly the protocol allowlist", () => {
    assert.deepEqual(Object.keys(componentRegistry).sort(), [
      "bar_chart",
      "citation_list",
      "line_chart",
      "metric",
      "pie_chart",
      "table",
      "text",
      "video_evidence",
    ]);
  });

  it("fails closed to safe text for malformed payloads", () => {
    const markup = renderToStaticMarkup(
      createElement(GenUIRenderer, {
        payload: { version: "1.0", type: "unknown", html: "<script>alert(1)</script>" },
        fallbackText: "Safe textual answer.",
      }),
    );
    assert.match(markup, /Safe textual answer\./);
    assert.doesNotMatch(markup, /<script>|alert\(1\)/);
  });

  it("contains no dynamic import, eval, or raw HTML rendering path", () => {
    const source = readFileSync(resolve(process.cwd(), "src/genui/renderer.tsx"), "utf8");
    assert.doesNotMatch(source, /\beval\s*\(|\bFunction\s*\(|\bimport\s*\(/);
    assert.doesNotMatch(source, /dangerouslySetInnerHTML/);
  });

  it("uses the required Recharts visualization primitives", () => {
    const source = readFileSync(resolve(process.cwd(), "src/genui/renderer.tsx"), "utf8");
    assert.match(source, /BarChart/);
    assert.match(source, /LineChart/);
    assert.match(source, /PieChart/);
    assert.match(source, /ResponsiveContainer/);
  });
});
