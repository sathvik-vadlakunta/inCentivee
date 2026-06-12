import { defineConfig } from 'astro/config'
import tailwindcss from '@tailwindcss/vite'
import sitemap from '@astrojs/sitemap'
import cloudflare from '@astrojs/cloudflare'
import markdoc from '@astrojs/markdoc'
import keystatic from '@keystatic/astro'

import practice from './src/data/practice.json'

export default defineConfig({
  site: `https://${practice.domain}`,
  adapter: cloudflare(),
  vite: {
    plugins: [tailwindcss()],
  },
  integrations: [
    sitemap({
      changefreq: 'weekly',
      priority: 0.7,
      lastmod: new Date(),
    }),
    markdoc(),
    keystatic(),
  ],
})
