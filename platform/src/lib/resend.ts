/**
 * Email outreach via Resend.
 * Free tier: 3,000 emails/month (100/day).
 * Rate limiting is enforced here to stay within PKE compliance.
 */
import { Resend } from "resend";
import { db } from "./db";

export const resend = new Resend(process.env.RESEND_API_KEY);

const FROM = `${process.env.OUTREACH_FROM_NAME || "AI Web Generator"} <${process.env.OUTREACH_FROM_EMAIL || "demo@yourplatform.pl"}>`;

export interface OutreachEmailData {
  to: string;
  businessName: string;
  demoUrl: string;
  variant: "A" | "B" | "C";
  unsubscribeToken: string;
  subject: string;
  bodyHtml: string;
}

export async function sendOutreachEmail(data: OutreachEmailData) {
  const unsubscribeUrl = `${process.env.NEXT_PUBLIC_APP_URL}/unsubscribe?token=${data.unsubscribeToken}`;

  // Add mandatory PKE compliance footer to all emails
  const complianceFooter = `
    <div style="margin-top:32px;padding-top:16px;border-top:1px solid #e5e7eb;font-size:12px;color:#6b7280;font-family:Arial,sans-serif;">
      <p>Wiadomość wysłana przez: AI Web Generator | yourplatform.pl</p>
      <p>Dane firmowe pozyskaliśmy z publicznie dostępnych źródeł (Google Maps, OpenStreetMap).</p>
      <p>Jeśli nie życzą sobie Państwo otrzymywać wiadomości od nas:
        <a href="${unsubscribeUrl}" style="color:#6366f1;">wypisz się tutaj</a>
      </p>
    </div>
  `;

  const result = await resend.emails.send({
    from: FROM,
    to: data.to,
    subject: data.subject,
    html: data.bodyHtml + complianceFooter,
    headers: {
      "List-Unsubscribe": `<${unsubscribeUrl}>`,
      "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    },
    tags: [
      { name: "variant", value: data.variant },
      { name: "business", value: data.businessName.slice(0, 50) },
    ],
  });

  return result;
}

export async function processCampaignBatch(campaignId: string, batchSize: number = 20) {
  // Get pending leads for this campaign (not yet sent)
  const pendingLeads = await db.campaignLead.findMany({
    where: { campaignId, sentAt: null, unsubscribed: false },
    include: { lead: true, campaign: true },
    take: batchSize,
  });

  const results = [];
  for (const cl of pendingLeads) {
    if (!cl.lead.email) continue;

    // Generate unsubscribe token
    const unsubToken = await db.unsubscribeToken.create({
      data: { email: cl.lead.email },
    });

    try {
      // In production, email content comes from the GeneratedContent stored in lead.contentJson
      const content = cl.lead.contentJson as Record<string, unknown> | null;
      const outreachData = content?.outreach as Record<string, string[]> | null;

      const variant = (cl.variantUsed || "A") as "A" | "B" | "C";
      const variants = outreachData?.variants as Array<{ subject: string; body_html: string }> | undefined;
      const variantIndex = { A: 0, B: 1, C: 2 }[variant];
      const emailVariant = variants?.[variantIndex];

      if (!emailVariant) {
        console.warn(`No email content for lead ${cl.leadId}, variant ${variant}`);
        continue;
      }

      await sendOutreachEmail({
        to: cl.lead.email,
        businessName: cl.lead.name,
        demoUrl: cl.lead.demoSiteUrl || "",
        variant,
        unsubscribeToken: unsubToken.token,
        subject: emailVariant.subject,
        bodyHtml: emailVariant.body_html,
      });

      // Update records
      await db.campaignLead.update({
        where: { id: cl.id },
        data: { sentAt: new Date() },
      });
      await db.activity.create({
        data: {
          leadId: cl.leadId,
          type: "EMAIL_SENT",
          metadata: { campaignId, variant },
        },
      });
      await db.lead.update({
        where: { id: cl.leadId },
        data: {
          outreachSentAt: new Date(),
          lastActivityAt: new Date(),
          stage: "OUTREACH_SENT",
        },
      });

      results.push({ leadId: cl.leadId, status: "sent" });
    } catch (error) {
      console.error(`Failed to send email for lead ${cl.leadId}:`, error);
      results.push({ leadId: cl.leadId, status: "error", error: String(error) });
    }

    // Small delay between sends (deliverability best practice)
    await new Promise((r) => setTimeout(r, 500));
  }

  return results;
}
