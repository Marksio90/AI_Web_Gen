/**
 * Health check endpoint — used by Docker healthchecks and Nginx.
 * Returns 200 when the Next.js app is running and DB is reachable.
 */
import { NextResponse } from "next/server";
import { db } from "@/lib/db";

export const dynamic = "force-dynamic";

export async function GET() {
  let dbStatus = "ok";
  try {
    await db.$queryRaw`SELECT 1`;
  } catch {
    dbStatus = "error";
  }

  const status = dbStatus === "ok" ? "healthy" : "degraded";
  const code = status === "healthy" ? 200 : 503;

  return NextResponse.json(
    {
      status,
      version: process.env.npm_package_version || "1.0.0",
      timestamp: new Date().toISOString(),
      services: { database: dbStatus },
    },
    { status: code },
  );
}
