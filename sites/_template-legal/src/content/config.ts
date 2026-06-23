import { defineCollection, z } from 'astro:content'

// "services" = practice areas, "team" = attorneys, "locations" = areas-served city pages.
const services = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    description: z.string(),
    category: z.string(),
    order: z.number().default(0),
    image: z.string().optional(),
    faqs: z.array(z.object({ question: z.string(), answer: z.string() })).optional(),
  }),
})

const team = defineCollection({
  type: 'content',
  schema: z.object({
    name: z.string(),
    credentials: z.string(),
    title: z.string(),
    photo: z.string().optional(),
    specialties: z.array(z.string()).default([]),
    education: z.array(z.string()).default([]),
    barAdmissions: z.array(z.string()).default([]),
    sameAs: z.array(z.string()).default([]),
    order: z.number().default(0),
  }),
})

const locations = defineCollection({
  type: 'content',
  schema: z.object({
    city: z.string(),
    state: z.string(),
    title: z.string().optional(),
    description: z.string(),
    practiceAreas: z.array(z.string()).default([]),
    nearbyOffice: z.string().optional(),
    driveTime: z.string().optional(),
    order: z.number().default(0),
  }),
})

const blog = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    description: z.string(),
    pubDate: z.date(),
    updatedDate: z.date().optional(),
    author: z.string().default(''),
    image: z.string().optional(),
    tags: z.array(z.string()).default([]),
    draft: z.boolean().default(false),
  }),
})

export const collections = { services, team, locations, blog }
