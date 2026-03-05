/**
 * PKE-compliant one-click unsubscribe endpoint.
 * Required by Poland's Electronic Communications Law (Nov 2024).
 */
import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";

export async function GET(request: NextRequest) {
  const token = request.nextUrl.searchParams.get("token");
  if (!token) {
    return NextResponse.json({ error: "No token" }, { status: 400 });
  }

  const record = await db.unsubscribeToken.findUnique({ where: { token } });
  if (!record || record.usedAt) {
    return new NextResponse(
      `<html><body><p>Link wygasł lub był już użyty.</p></body></html>`,
      { headers: { "Content-Type": "text/html" } },
    );
  }

  // Mark as unsubscribed
  await db.unsubscribeToken.update({ where: { token }, data: { usedAt: new Date() } });

  // Mark all campaign leads for this email as unsubscribed
  const lead = await db.lead.findFirst({ where: { email: record.email } });
  if (lead) {
    await db.campaignLead.updateMany({
      where: { leadId: lead.id },
      data: { unsubscribed: true },
    });
    await db.lead.update({
      where: { id: lead.id },
      data: { stage: "LOST", lastActivityAt: new Date() },
    });
    await db.activity.create({
      data: {
        leadId: lead.id,
        type: "UNSUBSCRIBED",
        metadata: { email: record.email },
      },
    });
  }

  return new NextResponse(
    `<!doctype html>
<html lang="pl">
<head><meta charset="UTF-8"><title>Wypisano z listy</title></head>
<body style="font-family:Arial,sans-serif;max-width:500px;margin:80px auto;padding:20px;text-align:center;">
  <h1 style="color:#1a1a2e;">Wypisano pomyślnie</h1>
  <p>Adres <strong>${record.email}</strong> został usunięty z naszej listy kontaktowej.</p>
  <p style="color:#6b7280;font-size:14px;">Nie będziesz otrzymywać od nas więcej wiadomości.</p>
</body>
</html>`,
    { headers: { "Content-Type": "text/html; charset=utf-8" } },
  );
}

// One-click unsubscribe POST (RFC 8058)
export async function POST(request: NextRequest) {
  return GET(request);
}
