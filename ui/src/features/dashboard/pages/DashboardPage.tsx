import { Title, Text } from '@mantine/core';

export function Component() {
  return (
    <>
      <Title order={2}>Dashboard</Title>
      <Text c="dimmed" mt="sm">
        Overview of your Lintel workspace.
      </Text>
    </>
  );
}
