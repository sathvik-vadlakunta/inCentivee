import { defineConfig } from 'astro/config'
import tailwindcss from '@tailwindcss/vite'
import sitemap from '@astrojs/sitemap'
import cloudflare from '@astrojs/cloudflare'
import markdoc from '@astrojs/markdoc'

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
      lastmod: new Date(),
      serialize(item) {
        const u = item.url
        if (/healinghandspt\.net\/$/.test(u)) item.priority = 1.0
        else if (/\/(services|about|contact|testimonials)\/?$/.test(u)) item.priority = 0.9
        else if (/\/services\//.test(u)) item.priority = 0.8
        else if (/\/blog\//.test(u)) item.priority = 0.6
        else item.priority = 0.7
        return item
      },
    }),
    markdoc(),
  ],
})
