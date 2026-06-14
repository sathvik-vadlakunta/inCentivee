import { defineCollection, z } from 'astro:content'

const services = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    description: z.string(),
    category: z.string(),
    order: z.number().default(0),
    image: z.string().optional(),
    faqs: z
      .array(
        z.object({
          question: z.string(),
          answer: z.string(),
        }),
      )
      .optional(),
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

export const collections = { services, team, blog }
