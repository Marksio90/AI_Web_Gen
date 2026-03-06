/**
 * Server-Sent Events endpoint for real-time pipeline progress.
 *
 * Usage (EventSource):
 *   const es = new EventSource('/api/pipeline/stream?leadId=xxx')
 *   es.onmessage = (e) => console.log(JSON.parse(e.data))
 *
 * Events emitted:
 *   { type: 'stage', stage: 'ANALYZING', message: '...' }
 *   { type: 'complete', demoSiteUrl: '...', qcScore: 88 }
 *   { type: 'error', message: '...' }
 *   { type: 'heartbeat' }   — every 15s to keep connection alive
 */
import { NextRequest } from "next/server";
import { db } from "@/lib/db";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const PIPELINE_STAGE_MESSAGES: Record<string, string> = {
  DISCOVERED:     "Firma odkryta — w kolejce",
  ANALYZING:      "Analizuję stronę i SEO...",
  DESIGNING:      "Dopasowuję szablon i kolory...",
  GENERATING:     "Generuję treści po polsku (AI)...",
  QC_REVIEWING:   "Kontrola jakości...",
  QC_REVISION:    "Poprawki treści (iteracja QC)...",
  BUILDING_SITE:  "Buduję stronę Astro...",
  UPLOADING:      "Wgrywam do Cloudflare R2...",
  WRITING_EMAIL:  "Przygotowuję email outreach...",
  SITE_GENERATED: "✅ Strona gotowa!",
  OUTREACH_SENT:  "📧 Email wysłany!",
};

export async function GET(request: NextRequest) {
  const leadId = request.nextUrl.searchParams.get("leadId");

  const headers = new Headers({
    "Content-Type":  "text/event-stream",
    "Cache-Control": "no-cache, no-transform",
    "Connection":    "keep-alive",
    "X-Accel-Buffering": "no",   // disable nginx buffering
  });

  const encoder = new TextEncoder();
  let closed = false;
  let heartbeatInterval: ReturnType<typeof setInterval>;
  let pollInterval: ReturnType<typeof setInterval>;

  const stream = new ReadableStream({
    start(controller) {
      const emit = (data: object) => {
        if (closed) return;
        try {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(data)}\n\n`));
        } catch {
          closed = true;
        }
      };

      // Heartbeat — keeps proxy and browser alive
      heartbeatInterval = setInterval(() => {
        emit({ type: "heartbeat", ts: Date.now() });
      }, 15_000);

      // If no leadId, stream system stats
      if (!leadId) {
        pollInterval = setInterval(async () => {
          try {
            const [total, generated, outreach, converted] = await Promise.all([
              db.lead.count(),
              db.lead.count({ where: { stage: "SITE_GENERATED" } }),
              db.lead.count({ where: { stage: "OUTREACH_SENT" } }),
              db.lead.count({ where: { stage: "CONVERTED" } }),
            ]);
            emit({ type: "stats", total, generated, outreach, converted, ts: Date.now() });
          } catch { /* DB error — skip */ }
        }, 5_000);

        emit({ type: "connected", message: "Streaming system stats every 5s" });
        return;
      }

      // Single lead pipeline progress
      let lastStage = "";
      let lastActivity = 0;

      emit({ type: "connected", leadId, message: "Tracking pipeline progress..." });

      pollInterval = setInterval(async () => {
        try {
          const lead = await db.lead.findUnique({
            where: { id: leadId },
            select: { stage: true, demoSiteUrl: true, qcScore: true, lastActivityAt: true },
          });

          if (!lead) {
            emit({ type: "error", message: "Lead not found" });
            clearInterval(pollInterval);
            controller.close();
            return;
          }

          // Emit on activity change
          const activityTs = lead.lastActivityAt?.getTime() ?? 0;
          if (lead.stage !== lastStage || activityTs !== lastActivity) {
            lastStage = lead.stage;
            lastActivity = activityTs;

            emit({
              type: "stage",
              stage: lead.stage,
              message: PIPELINE_STAGE_MESSAGES[lead.stage] || lead.stage,
              ts: Date.now(),
            });

            if (lead.stage === "SITE_GENERATED" || lead.stage === "OUTREACH_SENT") {
              emit({
                type: "complete",
                stage: lead.stage,
                demoSiteUrl: lead.demoSiteUrl,
                qcScore: lead.qcScore,
                message: "Pipeline zakończony pomyślnie!",
              });
              clearInterval(pollInterval);
              clearInterval(heartbeatInterval);
              setTimeout(() => {
                try { controller.close(); } catch { /* already closed */ }
              }, 1_000);
            }
          }
        } catch { /* transient DB error — continue polling */ }
      }, 2_000);
    },

    cancel() {
      closed = true;
      clearInterval(heartbeatInterval);
      clearInterval(pollInterval);
    },
  });

  return new Response(stream, { headers });
}
