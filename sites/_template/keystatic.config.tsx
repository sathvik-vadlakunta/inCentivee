import { config, fields, collection } from '@keystatic/core'

export default config({
  storage: { kind: 'local' },
  collections: {
    blog: collection({
      label: 'Blog Posts',
      slugField: 'title',
      path: 'src/content/blog/*',
      format: { contentField: 'content' },
      schema: {
        title: fields.slug({ name: { label: 'Title' } }),
        description: fields.text({ label: 'Description', multiline: true }),
        pubDate: fields.date({ label: 'Publish Date' }),
        author: fields.text({ label: 'Author' }),
        image: fields.image({
          label: 'Cover Image',
          directory: 'public/images/blog',
          publicPath: '/images/blog/',
        }),
        tags: fields.array(fields.text({ label: 'Tag' }), {
          label: 'Tags',
          itemLabel: (props) => props.value,
        }),
        draft: fields.checkbox({ label: 'Draft', defaultValue: true }),
        content: fields.markdoc({ label: 'Content' }),
      },
    }),
    services: collection({
      label: 'Services',
      slugField: 'title',
      path: 'src/content/services/*',
      format: { contentField: 'content' },
      schema: {
        title: fields.slug({ name: { label: 'Title' } }),
        description: fields.text({ label: 'Description', multiline: true }),
        category: fields.text({ label: 'Category' }),
        order: fields.integer({ label: 'Sort Order', defaultValue: 0 }),
        image: fields.image({
          label: 'Image',
          directory: 'public/images/services',
          publicPath: '/images/services/',
        }),
        faqs: fields.array(
          fields.object({
            question: fields.text({ label: 'Question' }),
            answer: fields.text({ label: 'Answer', multiline: true }),
          }),
          { label: 'FAQs', itemLabel: (props) => props.fields.question.value },
        ),
        content: fields.markdoc({ label: 'Content' }),
      },
    }),
    team: collection({
      label: 'Team Members',
      slugField: 'name',
      path: 'src/content/team/*',
      format: { contentField: 'content' },
      schema: {
        name: fields.slug({ name: { label: 'Name' } }),
        credentials: fields.text({ label: 'Credentials (e.g. DMD, DDS)' }),
        title: fields.text({ label: 'Title' }),
        photo: fields.image({
          label: 'Photo',
          directory: 'public/images/team',
          publicPath: '/images/team/',
        }),
        specialties: fields.array(fields.text({ label: 'Specialty' }), {
          label: 'Specialties',
          itemLabel: (props) => props.value,
        }),
        education: fields.array(fields.text({ label: 'Degree / School' }), {
          label: 'Education',
          itemLabel: (props) => props.value,
        }),
        order: fields.integer({ label: 'Sort Order', defaultValue: 0 }),
        content: fields.markdoc({ label: 'Bio' }),
      },
    }),
  },
})
