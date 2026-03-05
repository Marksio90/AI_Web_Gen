#!/usr/bin/env node
/**
 * Build a demo site for a specific business.
 * Called by the agent pipeline after content generation.
 *
 * Usage:
 *   node build-site.js --data '{"business":...,"content":...,"design":...}' --output ./dist/slug
 *   node build-site.js --file business-data.json --slug restaurant-warsaw-abc1
 *
 * After build, uploads to Cloudflare R2 if CF credentials are set.
 */

import { execSync } from "child_process";
import { writeFileSync, mkdirSync, rmSync } from "fs";
import { resolve, join } from "path";
import process from "process";

const args = process.argv.slice(2);
const getArg = (flag) => {
  const i = args.indexOf(flag);
  return i !== -1 ? args[i + 1] : null;
};

async function main() {
  const dataArg = getArg("--data");
  const fileArg = getArg("--file");
  const slugArg = getArg("--slug") || "demo-site";
  const outputArg = getArg("--output") || `./dist/${slugArg}`;

  if (!dataArg && !fileArg) {
    console.error("Error: provide --data JSON or --file path");
    process.exit(1);
  }

  let businessData;
  if (fileArg) {
    const { readFileSync } = await import("fs");
    businessData = JSON.parse(readFileSync(fileArg, "utf-8"));
  } else {
    businessData = JSON.parse(dataArg);
  }

  console.log(`Building site for: ${businessData.business?.name || "unknown"}`);

  // Set BUSINESS_DATA env var and trigger Astro build
  const env = {
    ...process.env,
    BUSINESS_DATA: JSON.stringify(businessData),
    SITE: `https://${slugArg}.${process.env.DEMO_BASE_DOMAIN || "demo.yourplatform.pl"}`,
    IS_DEMO: "true",
  };

  const outDir = resolve(outputArg);
  mkdirSync(outDir, { recursive: true });

  execSync(`npx astro build --outDir ${outDir}`, {
    cwd: resolve(import.meta.dirname, ".."),
    env,
    stdio: "inherit",
  });

  console.log(`Build complete: ${outDir}`);

  // Upload to Cloudflare R2 if configured
  if (process.env.CF_R2_ACCESS_KEY && process.env.CF_ACCOUNT_ID) {
    await uploadToR2(outDir, slugArg);
  }

  console.log(`Demo site ready: https://${slugArg}.${process.env.DEMO_BASE_DOMAIN || "demo.yourplatform.pl"}`);
}

async function uploadToR2(distDir, slug) {
  console.log(`Uploading to R2: ${slug}/`);
  try {
    // Uses wrangler r2 object put — requires wrangler CLI
    execSync(
      `npx wrangler r2 object put ${process.env.CF_R2_BUCKET || "demo-sites"}/${slug}/ --file ${distDir} --recursive`,
      { stdio: "inherit" }
    );
    console.log("R2 upload complete");
  } catch (e) {
    console.error("R2 upload failed:", e.message);
    console.log("(Deploy manually or configure Wrangler credentials)");
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
