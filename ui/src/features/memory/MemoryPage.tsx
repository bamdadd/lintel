import { useState } from 'react';
import { Title, Stack, Select, Tabs, Center, Text } from '@mantine/core';
import { IconBrain, IconTimeline, IconSearch } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { customInstance } from '@/shared/api/client';
import { MemoryList } from './MemoryList';
import { EpisodicTimeline } from './EpisodicTimeline';
import { MemorySearchBar } from './MemorySearchBar';

interface ProjectItem {
  project_id: string;
  name: string;
}

export function Component() {
  const [selectedProject, setSelectedProject] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string | null>('long_term');

  const { data: projectsResp } = useQuery({
    queryKey: ['/api/v1/projects'],
    queryFn: () => customInstance<{ data: ProjectItem[] }>('/api/v1/projects'),
  });

  const projects = (projectsResp?.data ?? []) as ProjectItem[];
  const projectOptions = projects.map((p) => ({
    value: p.project_id,
    label: p.name,
  }));

  return (
    <Stack gap="lg" p="md">
      <Title order={2}>Memory</Title>

      <Select
        label="Project"
        placeholder="Select a project to view memories"
        data={projectOptions}
        value={selectedProject}
        onChange={setSelectedProject}
        searchable
        clearable
        maw={400}
      />

      {!selectedProject && (
        <Center py="xl">
          <Text c="dimmed">Select a project to view memories</Text>
        </Center>
      )}

      {selectedProject && (
        <Tabs value={activeTab} onChange={setActiveTab}>
          <Tabs.List>
            <Tabs.Tab value="long_term" leftSection={<IconBrain size={16} />}>
              Long-term
            </Tabs.Tab>
            <Tabs.Tab value="episodic" leftSection={<IconTimeline size={16} />}>
              Episodic
            </Tabs.Tab>
            <Tabs.Tab value="search" leftSection={<IconSearch size={16} />}>
              Search
            </Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="long_term" pt="md">
            <MemoryList projectId={selectedProject} memoryType="long_term" />
          </Tabs.Panel>

          <Tabs.Panel value="episodic" pt="md">
            <EpisodicTimeline projectId={selectedProject} />
          </Tabs.Panel>

          <Tabs.Panel value="search" pt="md">
            <MemorySearchBar projectId={selectedProject} />
          </Tabs.Panel>
        </Tabs>
      )}
    </Stack>
  );
}
