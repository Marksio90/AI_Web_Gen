import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import { processCampaignBatch } from "@/lib/resend";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id: campaignId } = await params;
  const body = await request.json().catch(() => ({}));
  const batchSize = Math.min(body.batchSize ?? 20, 100);

  const campaign = await db.campaign.findUnique({ where: { id: campaignId } });
  if (!campaign) return NextResponse.json({ error: "Campaign not found" }, { status: 404 });
  if (campaign.status === "COMPLETED") {
    return NextResponse.json({ error: "Campaign already completed" }, { status: 400 });
  }

  // Mark as running
  await db.campaign.update({
    where: { id: campaignId },
    data: { status: "RUNNING" },
  });

  const results = await processCampaignBatch(campaignId, batchSize);
  const sentCount = results.filter((r) => r.status === "sent").length;

  // Check if campaign is fully sent
  const remaining = await db.campaignLead.count({
    where: { campaignId: campaignId, sentAt: null, unsubscribed: false },
  });

  await db.campaign.update({
    where: { id: campaignId },
    data: {
      sentCount: { increment: sentCount },
      status: remaining === 0 ? "COMPLETED" : "RUNNING",
      completedAt: remaining === 0 ? new Date() : undefined,
    },
  });

  return NextResponse.json({
    sent: sentCount,
    errors: results.filter((r) => r.status === "error").length,
    remaining,
  });
}
