import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import { z } from "zod";

const LeadFilterSchema = z.object({
  stage: z.string().optional(),
  category: z.string().optional(),
  city: z.string().optional(),
  websiteStatus: z.string().optional(),
  search: z.string().optional(),
  page: z.coerce.number().default(1),
  limit: z.coerce.number().max(100).default(50),
});

export async function GET(request: NextRequest) {
  const params = Object.fromEntries(request.nextUrl.searchParams);
  const filters = LeadFilterSchema.safeParse(params);

  if (!filters.success) {
    return NextResponse.json({ error: "Invalid parameters" }, { status: 400 });
  }

  const { stage, category, city, websiteStatus, search, page, limit } = filters.data;
  const skip = (page - 1) * limit;

  const where = {
    ...(stage && { stage: stage as never }),
    ...(category && { category: category as never }),
    ...(city && { city: { contains: city, mode: "insensitive" as const } }),
    ...(websiteStatus && { websiteStatus: websiteStatus as never }),
    ...(search && {
      OR: [
        { name: { contains: search, mode: "insensitive" as const } },
        { city: { contains: search, mode: "insensitive" as const } },
        { email: { contains: search, mode: "insensitive" as const } },
      ],
    }),
  };

  const [leads, total] = await Promise.all([
    db.lead.findMany({
      where,
      skip,
      take: limit,
      orderBy: { createdAt: "desc" },
      select: {
        id: true,
        name: true,
        city: true,
        category: true,
        stage: true,
        websiteStatus: true,
        email: true,
        phone: true,
        demoSiteUrl: true,
        qcScore: true,
        rating: true,
        reviewCount: true,
        outreachSentAt: true,
        lastActivityAt: true,
        createdAt: true,
      },
    }),
    db.lead.count({ where }),
  ]);

  return NextResponse.json({
    leads,
    pagination: {
      page,
      limit,
      total,
      pages: Math.ceil(total / limit),
    },
  });
}

const CreateLeadSchema = z.object({
  placeId: z.string(),
  name: z.string().min(1),
  address: z.string(),
  city: z.string(),
  phone: z.string().optional(),
  email: z.string().email().optional(),
  websiteUrl: z.string().url().optional(),
  category: z.string().optional(),
  googleMapsUrl: z.string().optional(),
  rating: z.number().optional(),
  reviewCount: z.number().optional(),
  source: z.string().default("google_maps"),
});

export async function POST(request: NextRequest) {
  const body = await request.json();
  const data = CreateLeadSchema.safeParse(body);

  if (!data.success) {
    return NextResponse.json({ error: data.error.flatten() }, { status: 400 });
  }

  // Upsert to handle re-discovered businesses
  const lead = await db.lead.upsert({
    where: { placeId: data.data.placeId },
    create: {
      ...data.data,
      category: (data.data.category as never) || "OTHER",
    },
    update: {
      // Update contact info if we got better data
      phone: data.data.phone ?? undefined,
      email: data.data.email ?? undefined,
      rating: data.data.rating ?? undefined,
      reviewCount: data.data.reviewCount ?? undefined,
    },
  });

  await db.activity.create({
    data: {
      leadId: lead.id,
      type: "DISCOVERED",
      metadata: { source: data.data.source },
    },
  });

  return NextResponse.json(lead, { status: 201 });
}
