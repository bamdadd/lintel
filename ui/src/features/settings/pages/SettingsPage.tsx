import { Title, Text } from '@mantine/core';

export function Component() {
  return (
    <>
      <Title order={2}>Settings</Title>
      <Text c="dimmed" mt="sm">
        Platform configuration
      </Text>
    </>
  );
}
