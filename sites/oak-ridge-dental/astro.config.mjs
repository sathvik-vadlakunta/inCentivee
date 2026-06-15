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
      // Per-page priority / changefreq so search engines understand the hierarchy
      serialize(item) {
        const path = new URL(item.url).pathname
        if (path === '/') {
          item.priority = 1.0
          item.changefreq = 'weekly'
        } else if (['/contact', '/new-patients', '/services', '/financing', '/reviews', '/team', '/about'].includes(path.replace(/\/$/, ''))) {
          item.priority = 0.9
          item.changefreq = 'monthly'
        } else if (path.startsWith('/services/') || path.startsWith('/dentist/') || path.startsWith('/team/')) {
          item.priority = 0.8
          item.changefreq = 'monthly'
        } else if (path.startsWith('/blog/')) {
          item.priority = 0.6
          item.changefreq = 'monthly'
        }
        return item
      },
    }),
    markdoc(),
    keystatic(),
  ],
})
