import Stripe from "stripe";

export const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!, {
  apiVersion: "2025-01-27.acacia",
  typescript: true,
});

export const PLANS = {
  STARTER: {
    name: "Starter",
    priceId: process.env.STRIPE_PRICE_STARTER!,
    price: 29,
    currency: "pln",
    features: [
      "1 strona wizytówkowa",
      "Hosting na naszej domenie",
      "Certyfikat SSL",
      "Aktualizacje treści (1/miesiąc)",
    ],
  },
  BUSINESS: {
    name: "Business",
    priceId: process.env.STRIPE_PRICE_BUSINESS!,
    price: 79,
    currency: "pln",
    features: [
      "Do 5 podstron",
      "Formularz kontaktowy",
      "Google Analytics",
      "Aktualizacje treści (4/miesiąc)",
      "Priorytetowe wsparcie",
    ],
  },
  PRO: {
    name: "Pro",
    priceId: process.env.STRIPE_PRICE_PRO!,
    price: 129,
    currency: "pln",
    features: [
      "Nieograniczone podstrony",
      "Własna domena (.pl gratis)",
      "Sklep online (do 50 produktów)",
      "Blog",
      "Aktualizacje treści (nielimitowane)",
      "Dedykowany opiekun",
    ],
  },
} as const;

export type PlanKey = keyof typeof PLANS;

export async function createCheckoutSession(
  leadId: string,
  planKey: PlanKey,
  customerEmail: string,
  successUrl: string,
  cancelUrl: string,
) {
  const plan = PLANS[planKey];

  const session = await stripe.checkout.sessions.create({
    payment_method_types: ["card", "blik", "p24"],
    mode: "subscription",
    customer_email: customerEmail,
    line_items: [{ price: plan.priceId, quantity: 1 }],
    metadata: { leadId, plan: planKey },
    success_url: successUrl,
    cancel_url: cancelUrl,
    locale: "pl",
    subscription_data: {
      metadata: { leadId, plan: planKey },
    },
  });

  return session;
}

export async function createPortalSession(stripeCustomerId: string, returnUrl: string) {
  return stripe.billingPortal.sessions.create({
    customer: stripeCustomerId,
    return_url: returnUrl,
  });
}
