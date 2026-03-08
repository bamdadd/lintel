import { Alert, Button, Code, Stack, Text } from '@mantine/core';
import { useRouteError, isRouteErrorResponse } from 'react-router';

const isDev = import.meta.env.DEV;

export function RouteError() {
  const error = useRouteError();

  let title = 'Something went wrong';
  let message = 'This section encountered an error. Try refreshing the page.';
  let stack: string | undefined;

  if (isRouteErrorResponse(error)) {
    title = `${error.status} ${error.statusText}`;
    message = typeof error.data === 'string' ? error.data : JSON.stringify(error.data);
  } else if (error instanceof Error) {
    title = error.name || 'Error';
    message = error.message;
    stack = error.stack;
  } else if (typeof error === 'string') {
    message = error;
  }

  return (
    <Stack align="center" py="xl" maw={800} mx="auto">
      <Alert color="red" title={title} w="100%">
        <Text size="sm">{message}</Text>
        {isDev && stack && (
          <Code block mt="sm" style={{ whiteSpace: 'pre-wrap', fontSize: 11, maxHeight: 400, overflow: 'auto' }}>
            {stack}
          </Code>
        )}
      </Alert>
      <Button onClick={() => window.location.reload()}>Refresh</Button>
    </Stack>
  );
}
