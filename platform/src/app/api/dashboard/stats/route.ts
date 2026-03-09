import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import { verifyAuth } from "@/lib/auth";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const auth = await verifyAuth(request);
  if (auth instanceof NextResponse) return auth;

  const [
    totalLeads,
    sitesGenerated,
    emailsSent,
    conversions,
    stageBreakdown,
    categoryBreakdown,
    recentActivity,
  ] = await Promise.all([
    db.lead.count(),
    db.lead.count({ where: { demoSiteUrl: { not: null } } }),
    db.lead.count({ where: { outreachSentAt: { not: null } } }),
    db.lead.count({ where: { stage: "CONVERTED" } }),

    db.lead.groupBy({
      by: ["stage"],
      _count: { stage: true },
      orderBy: { _count: { stage: "desc" } },
    }),

    db.lead.groupBy({
      by: ["category"],
      _count: { category: true },
      orderBy: { _count: { category: "desc" } },
      take: 10,
    }),

    db.activity.findMany({
      take: 20,
      orderBy: { createdAt: "desc" },
      include: { lead: { select: { name: true } } },
    }),
  ]);

  const conversionRate = totalLeads > 0
    ? ((conversions / totalLeads) * 100).toFixed(1)
    : "0";

  // Cost estimation based on model pricing
  // gpt-4o-mini agents (crawler, seo, design, email): ~$0.003 per business
  // gpt-4o / Groq (content, qc): ~$0.05 per business (gpt-4o) or ~$0.005 (Groq)
  const costPerSite = 0.012; // blended average with Groq for content
  const groqShare = 0.3; // approximate Groq proportion of total cost

  const response = NextResponse.json({
    totalLeads,
    sitesGenerated,
    emailsSent,
    conversions,
    conversionRate,
    stageBreakdown: stageBreakdown.map((s) => ({
      stage: s.stage,
      count: s._count.stage,
    })),
    categoryBreakdown: categoryBreakdown.map((c) => ({
      category: c.category,
      count: c._count.category,
    })),
    recentActivity: recentActivity.map((a) => ({
      id: a.id,
      leadName: a.lead.name,
      type: a.type,
      createdAt: a.createdAt.toISOString(),
    })),
    monthlyCost: {
      openai: Number((sitesGenerated * costPerSite * (1 - groqShare)).toFixed(2)),
      groq: Number((sitesGenerated * costPerSite * groqShare).toFixed(2)),
      total: Number((sitesGenerated * costPerSite).toFixed(2)),
    },
  });

  // Cache for 30 seconds — dashboard doesn't need real-time data
  response.headers.set("Cache-Control", "private, max-age=30, stale-while-revalidate=60");

  return response;
}
