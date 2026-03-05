import { defineConfig } from "astro/config";
import tailwind from "@astrojs/tailwind";
import sitemap from "@astrojs/sitemap";

export default defineConfig({
  integrations: [tailwind(), sitemap()],
  output: "static",
  // Site URL injected at build time via SITE env var
  site: process.env.SITE || "https://demo.yourplatform.pl",
});
