import { defineConfig } from 'orval';

export default defineConfig({
  lintel: {
    input: {
      target: '../openapi.json',
    },
    output: {
      mode: 'tags-split',
      target: 'src/generated/api',
      schemas: 'src/generated/models',
      client: 'react-query',
      override: {
        mutator: {
          path: 'src/shared/api/client.ts',
          name: 'customInstance',
        },
        query: {
          useQuery: true,
          useMutation: true,
        },
      },
    },
  },
});
