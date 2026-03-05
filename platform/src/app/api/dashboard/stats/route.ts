import { NextResponse } from "next/server";
import { db } from "@/lib/db";

export async function GET() {
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
      take: 8,
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

  return NextResponse.json({
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
    // Cost tracking would come from actual API usage logs
    // Using estimates based on processed count
    monthlyCost: {
      openai: sitesGenerated * 0.05,
      groq: sitesGenerated * 0.005,
      total: sitesGenerated * 0.055,
    },
  });
}
