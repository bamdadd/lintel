import { Alert, Button, Stack } from '@mantine/core';

export function RouteError() {
  return (
    <Stack align="center" py="xl">
      <Alert color="red" title="Something went wrong">
        This section encountered an error. Try refreshing the page.
      </Alert>
      <Button onClick={() => window.location.reload()}>Refresh</Button>
    </Stack>
  );
}
