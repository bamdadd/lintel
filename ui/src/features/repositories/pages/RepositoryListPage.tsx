import { Title, Text } from '@mantine/core';

export function Component() {
  return (
    <>
      <Title order={2}>Repositories</Title>
      <Text c="dimmed" mt="sm">
        Manage code repositories
      </Text>
    </>
  );
}
