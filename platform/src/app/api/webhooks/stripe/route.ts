/**
 * Stripe webhook handler.
 * Processes subscription events and updates lead status in DB.
 */
import { NextRequest, NextResponse } from "next/server";
import { stripe } from "@/lib/stripe";
import { db } from "@/lib/db";
import Stripe from "stripe";

export async function POST(request: NextRequest) {
  const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET;
  if (!webhookSecret) {
    console.error("STRIPE_WEBHOOK_SECRET not configured");
    return NextResponse.json({ error: "Server misconfiguration" }, { status: 500 });
  }

  const body = await request.text();
  const signature = request.headers.get("stripe-signature");

  if (!signature) {
    return NextResponse.json({ error: "No signature" }, { status: 400 });
  }

  let event: Stripe.Event;
  try {
    event = stripe.webhooks.constructEvent(body, signature, webhookSecret);
  } catch (err) {
    console.error("Webhook signature verification failed:", err);
    return NextResponse.json({ error: "Invalid signature" }, { status: 400 });
  }

  try {
    switch (event.type) {
      case "checkout.session.completed": {
        const session = event.data.object as Stripe.Checkout.Session;
        const { leadId, plan } = session.metadata || {};
        if (!leadId) break;

        await db.lead.update({
          where: { id: leadId },
          data: {
            stage: "CONVERTED",
            stripeCustomerId: session.customer as string,
            stripeSubscriptionId: session.subscription as string,
            subscriptionPlan: plan as never,
            subscribedAt: new Date(),
            lastActivityAt: new Date(),
          },
        });

        await db.activity.create({
          data: {
            leadId,
            type: "SUBSCRIBED",
            metadata: { plan, sessionId: session.id },
          },
        });
        break;
      }

      case "customer.subscription.deleted": {
        const sub = event.data.object as Stripe.Subscription;
        const lead = await db.lead.findFirst({
          where: { stripeSubscriptionId: sub.id },
        });
        if (lead) {
          await db.lead.update({
            where: { id: lead.id },
            data: {
              stage: "LOST",
              stripeSubscriptionId: null,
              subscriptionPlan: null,
            },
          });
        }
        break;
      }

      case "invoice.payment_failed": {
        const invoice = event.data.object as Stripe.Invoice;
        console.warn("Payment failed for:", invoice.customer);
        // In production: send payment failure notification email
        break;
      }
    }
  } catch (err) {
    console.error("Webhook handler error:", err);
    return NextResponse.json({ error: "Handler error" }, { status: 500 });
  }

  return NextResponse.json({ received: true });
}
