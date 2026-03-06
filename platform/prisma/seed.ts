/**
 * Seed the database with demo data for development.
 * Run: npm run db:seed
 */
import { PrismaClient } from "@prisma/client";

const db = new PrismaClient();

const DEMO_LEADS = [
  {
    placeId: "demo_restaurant_warsaw_001",
    name: "Restauracja Staropolska",
    address: "ul. Nowy Świat 15, 00-029 Warszawa",
    city: "Warszawa",
    phone: "+48 22 123 45 67",
    email: "kontakt@restauracja-staropolska.pl",
    category: "RESTAURANT" as const,
    googleMapsUrl: "https://maps.google.com/?q=Restauracja+Staropolska+Warszawa",
    rating: 4.3,
    reviewCount: 287,
    stage: "DISCOVERED" as const,
    websiteStatus: "NONE" as const,
    source: "demo",
  },
  {
    placeId: "demo_beauty_krakow_001",
    name: "Salon Urody Monika",
    address: "ul. Floriańska 12, 31-021 Kraków",
    city: "Kraków",
    phone: "+48 12 987 65 43",
    email: "biuro@salon-monika.pl",
    category: "BEAUTY_SALON" as const,
    rating: 4.7,
    reviewCount: 156,
    stage: "ANALYZED" as const,
    websiteStatus: "POOR" as const,
    source: "demo",
  },
  {
    placeId: "demo_dental_wroclaw_001",
    name: "Gabinet Stomatologiczny Dr Kowalski",
    address: "ul. Świdnicka 8, 50-067 Wrocław",
    city: "Wrocław",
    phone: "+48 71 234 56 78",
    email: "rejestracja@dr-kowalski.pl",
    category: "DENTAL_CLINIC" as const,
    rating: 4.9,
    reviewCount: 423,
    stage: "SITE_GENERATED" as const,
    websiteStatus: "NONE" as const,
    demoSiteUrl: "https://dr-kowalski-wroclaw-abc1.demo.yourplatform.pl",
    demoSiteSlug: "dr-kowalski-wroclaw-abc1",
    qcScore: 88,
    source: "demo",
  },
  {
    placeId: "demo_plumber_gdansk_001",
    name: "Hydraulik Marek — Awarie 24h",
    address: "ul. Długa 44, 80-827 Gdańsk",
    city: "Gdańsk",
    phone: "+48 58 345 67 89",
    category: "PLUMBER" as const,
    rating: 4.6,
    reviewCount: 89,
    stage: "OUTREACH_SENT" as const,
    websiteStatus: "NONE" as const,
    demoSiteUrl: "https://hydraulik-marek-gdansk-d4e5.demo.yourplatform.pl",
    demoSiteSlug: "hydraulik-marek-gdansk-d4e5",
    qcScore: 81,
    outreachSentAt: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000),
    source: "demo",
  },
  {
    placeId: "demo_fitness_poznan_001",
    name: "FitLife Siłownia Poznań",
    address: "ul. Święty Marcin 20, 61-806 Poznań",
    city: "Poznań",
    phone: "+48 61 456 78 90",
    email: "info@fitlife-poznan.pl",
    category: "FITNESS" as const,
    rating: 4.4,
    reviewCount: 312,
    stage: "CONVERTED" as const,
    websiteStatus: "NONE" as const,
    demoSiteUrl: "https://fitlife-poznan-f6g7.demo.yourplatform.pl",
    demoSiteSlug: "fitlife-poznan-f6g7",
    qcScore: 92,
    subscribedAt: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000),
    subscriptionPlan: "BUSINESS" as const,
    source: "demo",
  },
];

async function main() {
  console.log("Seeding database with demo data...");

  for (const leadData of DEMO_LEADS) {
    const lead = await db.lead.upsert({
      where: { placeId: leadData.placeId },
      create: leadData,
      update: {},
    });

    // Add discovery activity
    await db.activity.upsert({
      where: { id: `seed_activity_${lead.id}` },
      create: {
        id: `seed_activity_${lead.id}`,
        leadId: lead.id,
        type: "DISCOVERED",
        metadata: { source: "seed" },
      },
      update: {},
    });

    console.log(`✓ ${lead.name} (${lead.city}) — ${lead.stage}`);
  }

  console.log(`\nSeeded ${DEMO_LEADS.length} demo leads`);
}

main()
  .catch(console.error)
  .finally(() => db.$disconnect());
