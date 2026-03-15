import { createTheme } from '@mantine/core';

export const theme = createTheme({
  primaryColor: 'indigo',
  defaultRadius: 'md',
  fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
  headings: {
    fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
    fontWeight: '700',
  },
  components: {
    Table: {
      defaultProps: {
        verticalSpacing: 'sm',
        horizontalSpacing: 'md',
      },
    },
    Paper: {
      defaultProps: {
        shadow: 'none',
      },
    },
    Modal: {
      defaultProps: {
        overlayProps: { backgroundOpacity: 0.4, blur: 4 },
        transitionProps: { transition: 'pop', duration: 200 },
      },
    },
    Button: {
      defaultProps: {
        radius: 'md',
      },
    },
    ActionIcon: {
      defaultProps: {
        radius: 'md',
      },
    },
  },
});
