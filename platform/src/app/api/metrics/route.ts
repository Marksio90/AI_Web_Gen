/**
 * Prometheus metrics endpoint for the Next.js platform.
 * Scraped by Prometheus every 30s.
 *
 * Metrics exported:
 *   aiwebgen_leads_total{stage,category}
 *   aiwebgen_conversions_total
 *   aiwebgen_emails_sent_total
 *   aiwebgen_sites_generated_total
 *   aiwebgen_db_up
 */
import { NextResponse } from "next/server";
import { db } from "@/lib/db";

export const dynamic = "force-dynamic";

export async function GET() {
  const lines: string[] = [];

  const emit = (name: string, help: string, type: string, samples: string[]) => {
    lines.push(`# HELP ${name} ${help}`);
    lines.push(`# TYPE ${name} ${type}`);
    lines.push(...samples);
  };

  try {
    const [
      stageBreakdown,
      categoryBreakdown,
      conversions,
      emailsSent,
      sitesGenerated,
    ] = await Promise.all([
      db.lead.groupBy({ by: ["stage"], _count: { stage: true } }),
      db.lead.groupBy({ by: ["category"], _count: { category: true } }),
      db.lead.count({ where: { stage: "CONVERTED" } }),
      db.lead.count({ where: { outreachSentAt: { not: null } } }),
      db.lead.count({ where: { demoSiteUrl: { not: null } } }),
    ]);

    // Leads by stage
    emit(
      "aiwebgen_leads_total",
      "Total number of leads by pipeline stage",
      "gauge",
      stageBreakdown.map(
        (s) => `aiwebgen_leads_total{stage="${s.stage}"} ${s._count.stage}`
      )
    );

    // Leads by category
    emit(
      "aiwebgen_leads_by_category",
      "Total number of leads by business category",
      "gauge",
      categoryBreakdown.map(
        (c) => `aiwebgen_leads_by_category{category="${c.category}"} ${c._count.category}`
      )
    );

    emit("aiwebgen_conversions_total", "Total paying subscribers", "counter", [
      `aiwebgen_conversions_total ${conversions}`,
    ]);
    emit("aiwebgen_emails_sent_total", "Total outreach emails sent", "counter", [
      `aiwebgen_emails_sent_total ${emailsSent}`,
    ]);
    emit("aiwebgen_sites_generated_total", "Total demo sites generated", "counter", [
      `aiwebgen_sites_generated_total ${sitesGenerated}`,
    ]);
    emit("aiwebgen_db_up", "Database connectivity (1=up, 0=down)", "gauge", [
      "aiwebgen_db_up 1",
    ]);
  } catch {
    emit("aiwebgen_db_up", "Database connectivity (1=up, 0=down)", "gauge", [
      "aiwebgen_db_up 0",
    ]);
  }

  return new NextResponse(lines.join("\n") + "\n", {
    headers: { "Content-Type": "text/plain; version=0.0.4; charset=utf-8" },
  });
}
