/**
 * POST /api/leads/[id]/generate
 * Triggers the agent pipeline for a single lead.
 * Calls the Python FastAPI agent service.
 */
import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";

export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } },
) {
  const lead = await db.lead.findUnique({ where: { id: params.id } });
  if (!lead) return NextResponse.json({ error: "Lead not found" }, { status: 404 });

  if (lead.stage === "SITE_GENERATED" || lead.stage === "OUTREACH_SENT") {
    return NextResponse.json({ error: "Site already generated" }, { status: 400 });
  }

  // Call the Python agent pipeline service
  const agentApiUrl = process.env.AGENT_API_URL || "http://localhost:8000";
  const response = await fetch(`${agentApiUrl}/process`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Secret": process.env.AGENT_API_SECRET || "",
    },
    body: JSON.stringify({
      place_id: lead.placeId,
      name: lead.name,
      address: lead.address,
      city: lead.city,
      phone: lead.phone,
      email: lead.email,
      website_url: lead.websiteUrl,
      category: lead.category.toLowerCase(),
      rating: lead.rating,
      review_count: lead.reviewCount,
    }),
  });

  if (!response.ok) {
    const error = await response.text();
    return NextResponse.json({ error: `Agent pipeline error: ${error}` }, { status: 500 });
  }

  const result = await response.json();

  // Update lead with generated content
  await db.lead.update({
    where: { id: params.id },
    data: {
      stage: "SITE_GENERATED",
      demoSiteSlug: result.demo_site_slug,
      demoSiteUrl: result.demo_site_url,
      designSpecJson: result.design_spec,
      contentJson: result.content,
      qcScore: result.qc_result?.overall_score,
      lastActivityAt: new Date(),
    },
  });

  await db.activity.create({
    data: {
      leadId: params.id,
      type: "SITE_GENERATED",
      metadata: {
        demoSiteUrl: result.demo_site_url,
        qcScore: result.qc_result?.overall_score,
        durationS: result.pipeline_duration_s,
      },
    },
  });

  return NextResponse.json({ success: true, demoSiteUrl: result.demo_site_url });
}
