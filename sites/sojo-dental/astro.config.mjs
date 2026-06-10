import { defineConfig } from 'astro/config'
import tailwindcss from '@tailwindcss/vite'
import sitemap from '@astrojs/sitemap'
import cloudflare from '@astrojs/cloudflare'
import markdoc from '@astrojs/markdoc'
import keystatic from '@keystatic/astro'

export default defineConfig({
  site: 'https://sojodental.com',
  adapter: cloudflare(),
  vite: {
    plugins: [tailwindcss()],
  },
  integrations: [
    sitemap(),
    markdoc(),
    keystatic(),
  ],
})
