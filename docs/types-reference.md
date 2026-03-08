# Lintel Types Reference

> Auto-maintained by `/update-types` skill. Last updated: 2026-03-08.

## Contracts — Domain Types

### `src/lintel/contracts/types.py`

| Type | Kind | Line |
|------|------|------|
| ThreadRef | dataclass | 12 |
| ActorType | StrEnum | 27 |
| AgentCategory | StrEnum | 33 |
| AgentRole | StrEnum | 42 |
| WorkflowPhase | StrEnum | 59 |
| RepoStatus | StrEnum | 70 |
| Repository | dataclass | 77 |
| AIProviderType | StrEnum | 89 |
| AIProvider | dataclass | 100 |
| CredentialType | StrEnum | 112 |
| Credential | dataclass | 119 |
| SandboxStatus | StrEnum | 128 |
| SkillExecutionMode | StrEnum | 138 |
| ModelPolicy | dataclass | 145 |
| Model | dataclass | 156 |
| ModelAssignmentContext | StrEnum | 170 |
| ModelAssignment | dataclass | 181 |
| SkillDescriptor | dataclass | 192 |
| SkillResult | dataclass | 205 |
| SandboxConfig | dataclass | 214 |
| SandboxJob | dataclass | 226 |
| SandboxResult | dataclass | 235 |
| ProjectStatus | StrEnum | 246 |
| Project | dataclass | 253 |
| WorkItemStatus | StrEnum | 264 |
| WorkItemType | StrEnum | 274 |
| WorkItem | dataclass | 282 |
| PipelineStatus | StrEnum | 300 |
| StageStatus | StrEnum | 310 |
| Stage | dataclass | 322 |
| PipelineRun | dataclass | 340 |
| EnvironmentType | StrEnum | 357 |
| Environment | dataclass | 365 |
| Variable | dataclass | 375 |
| TriggerType | StrEnum | 388 |
| Trigger | dataclass | 397 |
| CodeArtifact | dataclass | 412 |
| TestVerdict | StrEnum | 424 |
| TestResult | dataclass | 432 |
| ApprovalStatus | StrEnum | 452 |
| ApprovalRequest | dataclass | 460 |
| AgentSession | dataclass | 477 |
| NotificationChannel | StrEnum | 493 |
| NotificationRule | dataclass | 500 |
| PolicyAction | StrEnum | 514 |
| Policy | dataclass | 522 |
| UserRole | StrEnum | 537 |
| User | dataclass | 544 |
| Team | dataclass | 556 |
| AuditEntry | dataclass | 569 |
| SkillCategory | StrEnum | 585 |
| SkillDefinition | dataclass | 600 |
| AgentDefinitionRecord | dataclass | 620 |
| WorkflowStepConfig | dataclass | 638 |
| WorkflowDefinitionRecord | dataclass | 651 |
| ResourceVersion | dataclass | 675 |
| PassedConstraint | dataclass | 684 |
| JobInput | dataclass | 692 |
| MCPServer | dataclass | 701 |
| ChatSession | dataclass | 713 |
| CorrelationId | NewType | 722 |
| EventId | NewType | 723 |

### `src/lintel/contracts/events.py`

| Type | Kind | Line |
|------|------|------|
| EventEnvelope | dataclass | 18 |
| ThreadMessageReceived | dataclass | 38 |
| PIIDetected | dataclass | 43 |
| PIIAnonymised | dataclass | 48 |
| PIIResidualRiskBlocked | dataclass | 53 |
| IntentRouted | dataclass | 61 |
| WorkflowStarted | dataclass | 66 |
| WorkflowAdvanced | dataclass | 71 |
| AgentStepScheduled | dataclass | 79 |
| AgentStepStarted | dataclass | 84 |
| AgentStepCompleted | dataclass | 89 |
| ModelSelected | dataclass | 94 |
| ModelCallCompleted | dataclass | 99 |
| SandboxJobScheduled | dataclass | 107 |
| SandboxCreated | dataclass | 112 |
| SandboxCommandExecuted | dataclass | 117 |
| SandboxFileWritten | dataclass | 122 |
| SandboxArtifactsCollected | dataclass | 127 |
| SandboxDestroyed | dataclass | 132 |
| CredentialStored | dataclass | 140 |
| CredentialRevoked | dataclass | 145 |
| RepositoryRegistered | dataclass | 153 |
| RepositoryUpdated | dataclass | 158 |
| RepositoryRemoved | dataclass | 163 |
| RepoCloned | dataclass | 168 |
| BranchCreated | dataclass | 173 |
| CommitPushed | dataclass | 178 |
| PRCreated | dataclass | 183 |
| PRCommentAdded | dataclass | 188 |
| HumanApprovalGranted | dataclass | 193 |
| HumanApprovalRejected | dataclass | 198 |
| SkillRegistered | dataclass | 206 |
| SkillUpdated | dataclass | 211 |
| SkillRemoved | dataclass | 216 |
| SkillInvoked | dataclass | 221 |
| SkillSucceeded | dataclass | 226 |
| SkillFailed | dataclass | 231 |
| VaultRevealRequested | dataclass | 239 |
| VaultRevealGranted | dataclass | 244 |
| PolicyDecisionRecorded | dataclass | 249 |
| ProjectCreated | dataclass | 257 |
| ProjectUpdated | dataclass | 262 |
| ProjectArchived | dataclass | 267 |
| ProjectRemoved | dataclass | 272 |
| WorkItemCreated | dataclass | 280 |
| WorkItemUpdated | dataclass | 285 |
| WorkItemCompleted | dataclass | 290 |
| WorkItemRemoved | dataclass | 295 |
| PipelineRunStarted | dataclass | 303 |
| PipelineStageCompleted | dataclass | 308 |
| PipelineRunCompleted | dataclass | 313 |
| PipelineRunFailed | dataclass | 318 |
| PipelineRunCancelled | dataclass | 323 |
| PipelineRunDeleted | dataclass | 328 |
| PipelineStageApproved | dataclass | 333 |
| PipelineStageRejected | dataclass | 338 |
| PipelineStageRetried | dataclass | 343 |
| StageReportEdited | dataclass | 348 |
| StageReportRegenerated | dataclass | 353 |
| ResourceVersionProduced | dataclass | 361 |
| ResourceVersionConsumed | dataclass | 366 |
| EnvironmentCreated | dataclass | 374 |
| EnvironmentUpdated | dataclass | 379 |
| EnvironmentRemoved | dataclass | 384 |
| TriggerCreated | dataclass | 392 |
| TriggerUpdated | dataclass | 397 |
| TriggerRemoved | dataclass | 402 |
| TriggerFired | dataclass | 407 |
| ArtifactStored | dataclass | 415 |
| TestRunCompleted | dataclass | 420 |
| ApprovalRequested | dataclass | 428 |
| ApprovalExpired | dataclass | 433 |
| NotificationSent | dataclass | 441 |
| UserCreated | dataclass | 449 |
| UserUpdated | dataclass | 454 |
| UserRemoved | dataclass | 459 |
| TeamCreated | dataclass | 464 |
| TeamUpdated | dataclass | 469 |
| TeamRemoved | dataclass | 474 |
| AIProviderCreated | dataclass | 482 |
| AIProviderUpdated | dataclass | 487 |
| AIProviderRemoved | dataclass | 492 |
| AIProviderApiKeyUpdated | dataclass | 497 |
| ModelRegistered | dataclass | 502 |
| ModelUpdated | dataclass | 507 |
| ModelRemoved | dataclass | 512 |
| ModelAssignmentCreated | dataclass | 517 |
| ModelAssignmentRemoved | dataclass | 522 |
| VariableCreated | dataclass | 530 |
| VariableUpdated | dataclass | 535 |
| VariableRemoved | dataclass | 540 |
| WorkflowDefinitionCreated | dataclass | 548 |
| WorkflowDefinitionUpdated | dataclass | 553 |
| WorkflowDefinitionRemoved | dataclass | 558 |
| NotificationRuleCreated | dataclass | 566 |
| NotificationRuleUpdated | dataclass | 571 |
| NotificationRuleRemoved | dataclass | 576 |
| MCPServerRegistered | dataclass | 584 |
| MCPServerUpdated | dataclass | 589 |
| MCPServerRemoved | dataclass | 594 |
| PolicyCreated | dataclass | 602 |
| PolicyUpdated | dataclass | 607 |
| PolicyRemoved | dataclass | 612 |
| ConnectionCreated | dataclass | 620 |
| ConnectionUpdated | dataclass | 625 |
| ConnectionRemoved | dataclass | 630 |
| SettingsUpdated | dataclass | 635 |
| ConversationCreated | dataclass | 643 |
| ConversationDeleted | dataclass | 648 |
| WorkflowTriggered | dataclass | 653 |
| ProjectSelected | dataclass | 658 |
| AgentDefinitionCreated | dataclass | 666 |
| AgentDefinitionUpdated | dataclass | 671 |
| AgentDefinitionRemoved | dataclass | 676 |
| ApprovalRequestCreated | dataclass | 684 |
| ApprovalRequestApproved | dataclass | 689 |
| ApprovalRequestRejected | dataclass | 694 |
| AuditRecorded | dataclass | 702 |

### `src/lintel/contracts/commands.py`

| Type | Kind | Line |
|------|------|------|
| ProcessIncomingMessage | dataclass | 14 |
| StartWorkflow | dataclass | 23 |
| ScheduleAgentStep | dataclass | 38 |
| ScheduleSandboxJob | dataclass | 47 |
| GrantApproval | dataclass | 57 |
| RejectApproval | dataclass | 66 |
| RegisterRepository | dataclass | 75 |
| UpdateRepository | dataclass | 86 |
| RemoveRepository | dataclass | 96 |
| StoreCredential | dataclass | 102 |
| RevokeCredential | dataclass | 112 |
| RevealPII | dataclass | 118 |

### `src/lintel/contracts/protocols.py`

| Type | Kind | Line |
|------|------|------|
| CommandDispatcher | Protocol | 29 |
| EventStore | Protocol | 35 |
| DeidentifyResult | Protocol | 63 |
| Deidentifier | Protocol | 71 |
| PIIVault | Protocol | 82 |
| ChannelAdapter | Protocol | 101 |
| ModelRouter | Protocol | 130 |
| SandboxManager | Protocol | 155 |
| CredentialStore | Protocol | 221 |
| RepositoryStore | Protocol | 244 |
| RepoProvider | Protocol | 260 |
| SkillRegistry | Protocol | 320 |

### `src/lintel/contracts/stream_events.py`

| Type | Kind | Line |
|------|------|------|
| StreamEvent | dataclass | 9 |
| InitializeStep | dataclass | 18 |
| StartStep | dataclass | 26 |
| FinishStep | dataclass | 32 |
| ToolCallEvent | dataclass | 40 |
| ToolResultEvent | dataclass | 50 |
| LogEvent | dataclass | 60 |
| StatusEvent | dataclass | 67 |
| EndEvent | dataclass | 73 |

### `src/lintel/contracts/errors.py`

| Type | Kind | Line |
|------|------|------|
| SandboxError | Exception | 4 |
| SandboxNotFoundError | Exception | 8 |
| SandboxTimeoutError | Exception | 16 |
| SandboxExecutionError | Exception | 20 |

## Config

### `src/lintel/config.py`

| Type | Kind | Line |
|------|------|------|
| DatabaseSettings | BaseSettings | 9 |
| NATSSettings | BaseSettings | 17 |
| SlackSettings | BaseSettings | 24 |
| PIISettings | BaseSettings | 32 |
| ModelSettings | BaseSettings | 39 |
| SandboxSettings | BaseSettings | 49 |
| Settings | BaseSettings | 59 |

## Domain

### `src/lintel/domain/graph_compiler.py`

| Type | Kind | Line |
|------|------|------|
| ThreadWorkflowState | TypedDict | 17 |

### `src/lintel/domain/chat_router.py`

| Type | Kind | Line |
|------|------|------|
| ChatRouterResult | dataclass | 41 |

### `src/lintel/domain/workflow_executor.py`

| Type | Kind | Line |
|------|------|------|
| StageCallback | TypeAlias | 44 |

### `src/lintel/domain/skills/protocols.py`

| Type | Kind | Line |
|------|------|------|
| Skill | Protocol | 11 |

### `src/lintel/domain/projections/protocols.py`

| Type | Kind | Line |
|------|------|------|
| Projection | Protocol | 11 |
| ProjectionEngine | Protocol | 22 |

## Workflows

### `src/lintel/workflows/state.py`

| Type | Kind | Line |
|------|------|------|
| ThreadWorkflowState | TypedDict | 9 |

## API — Request Models

### `src/lintel/api/routes/chat.py`

| Type | Kind | Line |
|------|------|------|
| StartConversationRequest | BaseModel | 52 |
| SendMessageRequest | BaseModel | 60 |

### `src/lintel/api/routes/pipelines.py`

| Type | Kind | Line |
|------|------|------|
| CreatePipelineRequest | BaseModel | 87 |
| ReportEditPayload | BaseModel | 599 |
| RegeneratePayload | BaseModel | 606 |

### `src/lintel/api/routes/workflows.py`

| Type | Kind | Line |
|------|------|------|
| StartWorkflowRequest | BaseModel | 18 |
| ProcessMessageRequest | BaseModel | 25 |

### `src/lintel/api/routes/projects.py`

| Type | Kind | Line |
|------|------|------|
| CreateProjectRequest | BaseModel | 53 |
| UpdateProjectRequest | BaseModel | 62 |

### `src/lintel/api/routes/agents.py`

| Type | Kind | Line |
|------|------|------|
| ScheduleAgentStepRequest | BaseModel | 66 |
| TestPromptRequest | BaseModel | 75 |
| CreateAgentDefinitionRequest | BaseModel | 121 |
| UpdateAgentDefinitionRequest | BaseModel | 132 |

### `src/lintel/api/routes/ai_providers.py`

| Type | Kind | Line |
|------|------|------|
| CreateAIProviderRequest | BaseModel | 114 |
| UpdateAIProviderRequest | BaseModel | 124 |
| UpdateAPIKeyRequest | BaseModel | 131 |

### `src/lintel/api/routes/models.py`

| Type | Kind | Line |
|------|------|------|
| CreateModelRequest | BaseModel | 110 |
| UpdateModelRequest | BaseModel | 122 |
| CreateModelAssignmentRequest | BaseModel | 132 |

### `src/lintel/api/routes/sandboxes.py`

| Type | Kind | Line |
|------|------|------|
| DevcontainerFeature | BaseModel | 171 |
| DevcontainerConfig | BaseModel | 178 |
| CreateSandboxRequest | BaseModel | 191 |
| ExecuteRequest | BaseModel | 200 |
| WriteFileRequest | BaseModel | 206 |

### `src/lintel/api/routes/repositories.py`

| Type | Kind | Line |
|------|------|------|
| RegisterRepoRequest | BaseModel | 23 |
| UpdateRepoRequest | BaseModel | 32 |

### `src/lintel/api/routes/credentials.py`

| Type | Kind | Line |
|------|------|------|
| StoreCredentialRequest | BaseModel | 73 |
| UpdateCredentialRequest | BaseModel | 81 |

### `src/lintel/api/routes/skills.py`

| Type | Kind | Line |
|------|------|------|
| RegisterSkillRequest | BaseModel | 93 |
| InvokeSkillRequest | BaseModel | 105 |
| UpdateSkillRequest | BaseModel | 168 |

### `src/lintel/api/routes/work_items.py`

| Type | Kind | Line |
|------|------|------|
| CreateWorkItemRequest | BaseModel | 47 |
| UpdateWorkItemRequest | BaseModel | 60 |

### `src/lintel/api/routes/variables.py`

| Type | Kind | Line |
|------|------|------|
| CreateVariableRequest | BaseModel | 66 |
| UpdateVariableRequest | BaseModel | 74 |

### `src/lintel/api/routes/triggers.py`

| Type | Kind | Line |
|------|------|------|
| CreateTriggerRequest | BaseModel | 66 |
| UpdateTriggerRequest | BaseModel | 75 |

### `src/lintel/api/routes/environments.py`

| Type | Kind | Line |
|------|------|------|
| CreateEnvironmentRequest | BaseModel | 44 |
| UpdateEnvironmentRequest | BaseModel | 51 |

### `src/lintel/api/routes/policies.py`

| Type | Kind | Line |
|------|------|------|
| CreatePolicyRequest | BaseModel | 47 |
| UpdatePolicyRequest | BaseModel | 57 |

### `src/lintel/api/routes/teams.py`

| Type | Kind | Line |
|------|------|------|
| CreateTeamRequest | BaseModel | 44 |
| UpdateTeamRequest | BaseModel | 51 |

### `src/lintel/api/routes/users.py`

| Type | Kind | Line |
|------|------|------|
| CreateUserRequest | BaseModel | 44 |
| UpdateUserRequest | BaseModel | 53 |

### `src/lintel/api/routes/notifications.py`

| Type | Kind | Line |
|------|------|------|
| CreateNotificationRuleRequest | BaseModel | 57 |
| UpdateNotificationRuleRequest | BaseModel | 66 |

### `src/lintel/api/routes/approval_requests.py`

| Type | Kind | Line |
|------|------|------|
| CreateApprovalRequestBody | BaseModel | 70 |
| DecisionBody | BaseModel | 78 |
| RejectBody | BaseModel | 82 |

### `src/lintel/api/routes/approvals.py`

| Type | Kind | Line |
|------|------|------|
| GrantApprovalRequest | BaseModel | 17 |
| RejectApprovalRequest | BaseModel | 26 |

### `src/lintel/api/routes/settings.py`

| Type | Kind | Line |
|------|------|------|
| ConnectionRequest | BaseModel | 39 |
| UpdateConnectionRequest | BaseModel | 46 |
| UpdateSettingsRequest | BaseModel | 51 |

### `src/lintel/api/routes/workflow_definitions.py`

| Type | Kind | Line |
|------|------|------|
| CreateWorkflowDefRequest | BaseModel | 62 |
| UpdateWorkflowDefRequest | BaseModel | 70 |

### `src/lintel/api/routes/pii.py`

| Type | Kind | Line |
|------|------|------|
| RevealPIIRequest | BaseModel | 18 |

### `src/lintel/api/routes/mcp_servers.py`

| Type | Kind | Line |
|------|------|------|
| CreateMCPServerRequest | BaseModel | 57 |
| UpdateMCPServerRequest | BaseModel | 66 |

### `src/lintel/api/routes/artifacts.py`

| Type | Kind | Line |
|------|------|------|
| CreateCodeArtifactRequest | BaseModel | 85 |
| CreateTestResultRequest | BaseModel | 95 |

### `src/lintel/api/routes/audit.py`

| Type | Kind | Line |
|------|------|------|
| CreateAuditEntryRequest | BaseModel | 49 |

## API — Response Schemas

### `src/lintel/api/schemas/health.py`

| Type | Kind | Line |
|------|------|------|
| HealthResponse | BaseModel | 6 |

### `src/lintel/api/schemas/chat.py`

| Type | Kind | Line |
|------|------|------|
| ChatMessageResponse | BaseModel | 6 |
| ConversationResponse | BaseModel | 15 |

### `src/lintel/api/schemas/pipelines.py`

| Type | Kind | Line |
|------|------|------|
| StageResponse | BaseModel | 8 |
| PipelineRunResponse | BaseModel | 19 |

### `src/lintel/api/schemas/workflows.py`

| Type | Kind | Line |
|------|------|------|
| WorkflowCommandResponse | BaseModel | 6 |
| WorkflowStatusResponse | BaseModel | 13 |

### `src/lintel/api/schemas/agents.py`

| Type | Kind | Line |
|------|------|------|
| TestPromptResponse | BaseModel | 8 |
| AgentStepCommandResponse | BaseModel | 14 |
| AgentDefinitionResponse | BaseModel | 22 |

### `src/lintel/api/schemas/ai_providers.py`

| Type | Kind | Line |
|------|------|------|
| AIProviderResponse | BaseModel | 8 |
| ProviderTypeInfo | BaseModel | 19 |
| APIKeyUpdateResponse | BaseModel | 26 |

### `src/lintel/api/schemas/models.py` (if exists)

See `src/lintel/api/routes/models.py` for model types.

### `src/lintel/api/schemas/sandboxes.py`

| Type | Kind | Line |
|------|------|------|
| CreateSandboxResponse | BaseModel | 6 |
| SandboxStatusResponse | BaseModel | 10 |
| ExecuteResponse | BaseModel | 15 |
| FileResponse | BaseModel | 21 |

### `src/lintel/api/schemas/repositories.py`

| Type | Kind | Line |
|------|------|------|
| RepositoryResponse | BaseModel | 6 |

### `src/lintel/api/schemas/credentials.py`

| Type | Kind | Line |
|------|------|------|
| CredentialResponse | BaseModel | 6 |

### `src/lintel/api/schemas/skills.py`

| Type | Kind | Line |
|------|------|------|
| SkillResponse | BaseModel | 8 |
| SkillInvocationResponse | BaseModel | 17 |

### `src/lintel/api/schemas/projects.py`

| Type | Kind | Line |
|------|------|------|
| ProjectResponse | BaseModel | 6 |

### `src/lintel/api/schemas/work_items.py`

| Type | Kind | Line |
|------|------|------|
| WorkItemResponse | BaseModel | 6 |

### `src/lintel/api/schemas/variables.py`

| Type | Kind | Line |
|------|------|------|
| VariableResponse | BaseModel | 6 |

### `src/lintel/api/schemas/triggers.py`

| Type | Kind | Line |
|------|------|------|
| TriggerResponse | BaseModel | 8 |

### `src/lintel/api/schemas/environments.py`

| Type | Kind | Line |
|------|------|------|
| EnvironmentResponse | BaseModel | 8 |

### `src/lintel/api/schemas/policies.py`

| Type | Kind | Line |
|------|------|------|
| PolicyResponse | BaseModel | 6 |

### `src/lintel/api/schemas/teams.py`

| Type | Kind | Line |
|------|------|------|
| TeamResponse | BaseModel | 6 |

### `src/lintel/api/schemas/users.py`

| Type | Kind | Line |
|------|------|------|
| UserResponse | BaseModel | 6 |

### `src/lintel/api/schemas/notifications.py`

| Type | Kind | Line |
|------|------|------|
| NotificationRuleResponse | BaseModel | 6 |

### `src/lintel/api/schemas/approval_requests.py`

| Type | Kind | Line |
|------|------|------|
| ApprovalRequestResponse | BaseModel | 6 |

### `src/lintel/api/schemas/approvals.py`

| Type | Kind | Line |
|------|------|------|
| ApprovalCommandResponse | BaseModel | 6 |

### `src/lintel/api/schemas/settings.py`

| Type | Kind | Line |
|------|------|------|
| ConnectionResponse | BaseModel | 8 |
| ConnectionTestResponse | BaseModel | 16 |
| SettingsResponse | BaseModel | 22 |

### `src/lintel/api/schemas/workflow_definitions.py`

| Type | Kind | Line |
|------|------|------|
| WorkflowDefinitionResponse | BaseModel | 8 |

### `src/lintel/api/schemas/artifacts.py`

| Type | Kind | Line |
|------|------|------|
| CodeArtifactResponse | BaseModel | 8 |
| TestResultResponse | BaseModel | 18 |

### `src/lintel/api/schemas/audit.py`

| Type | Kind | Line |
|------|------|------|
| AuditEntryResponse | BaseModel | 8 |

### `src/lintel/api/schemas/pii.py`

| Type | Kind | Line |
|------|------|------|
| RevealPIICommandResponse | BaseModel | 6 |
| VaultLogEntry | BaseModel | 15 |
| PiiStatsResponse | BaseModel | 24 |

### `src/lintel/api/schemas/threads.py`

| Type | Kind | Line |
|------|------|------|
| ThreadStatusResponse | BaseModel | 6 |

### `src/lintel/api/schemas/events.py`

| Type | Kind | Line |
|------|------|------|
| EventResponse | BaseModel | 8 |
| StreamEventsResponse | BaseModel | 12 |
| CorrelationEventsResponse | BaseModel | 18 |

### `src/lintel/api/schemas/metrics.py`

| Type | Kind | Line |
|------|------|------|
| PiiStatsResponse | BaseModel | 8 |
| PiiMetricsResponse | BaseModel | 16 |
| AgentMetricsResponse | BaseModel | 20 |
| SandboxOverview | BaseModel | 25 |
| ConnectionOverview | BaseModel | 29 |
| OverviewMetricsResponse | BaseModel | 33 |

### `src/lintel/api/schemas/admin.py`

| Type | Kind | Line |
|------|------|------|
| ResetProjectionsResponse | BaseModel | 6 |

### `src/lintel/api/schemas/mcp_servers.py` (if exists)

See `src/lintel/api/routes/mcp_servers.py` for request types.

## Infrastructure — Stores

### `src/lintel/infrastructure/persistence/crud_store.py`

| Type | Kind | Line |
|------|------|------|
| PostgresCrudStore | class | 58 |

### `src/lintel/infrastructure/persistence/dict_store.py`

| Type | Kind | Line |
|------|------|------|
| PostgresDictStore | class | 12 |

### `src/lintel/infrastructure/persistence/stores.py`

| Type | Kind | Line |
|------|------|------|
| PostgresRepositoryStore | class | 25 |
| PostgresAIProviderStore | class | 38 |
| PostgresMCPServerStore | class | 87 |
| PostgresCredentialStore | class | 99 |
| PostgresPolicyStore | class | 163 |
| PostgresEnvironmentStore | class | 175 |
| PostgresTeamStore | class | 182 |
| PostgresUserStore | class | 189 |
| PostgresTriggerStore | class | 196 |
| PostgresVariableStore | class | 203 |
| PostgresPipelineStore | class | 210 |
| PostgresApprovalRequestStore | class | 217 |
| PostgresNotificationRuleStore | class | 224 |
| PostgresAuditEntryStore | class | 231 |
| PostgresCodeArtifactStore | class | 238 |
| PostgresTestResultStore | class | 245 |
| PostgresProjectStore | class | 252 |
| PostgresWorkItemStore | class | 275 |
| PostgresChatStore | class | 300 |
| PostgresSandboxStore | class | 384 |
| PostgresAgentDefinitionStore | class | 406 |
| PostgresModelStore | class | 442 |
| PostgresModelAssignmentStore | class | 454 |
| PostgresSkillStore | class | 482 |

### `src/lintel/infrastructure/event_store/postgres.py`

| Type | Kind | Line |
|------|------|------|
| RecordLike | Protocol | 23 |
| PostgresEventStore | class | 30 |
| OptimisticConcurrencyError | Exception | 174 |
| IdempotencyViolationError | Exception | 178 |

### `src/lintel/infrastructure/event_store/in_memory.py`

| Type | Kind | Line |
|------|------|------|
| InMemoryEventStore | class | 14 |

## Infrastructure — Services

### `src/lintel/infrastructure/models/router.py`

| Type | Kind | Line |
|------|------|------|
| DefaultModelRouter | class | 23 |

### `src/lintel/infrastructure/sandbox/docker_backend.py`

| Type | Kind | Line |
|------|------|------|
| DockerSandboxManager | class | 28 |

### `src/lintel/infrastructure/channels/slack/adapter.py`

| Type | Kind | Line |
|------|------|------|
| SlackChannelAdapter | class | 15 |

### `src/lintel/infrastructure/pii/presidio_firewall.py`

| Type | Kind | Line |
|------|------|------|
| DeidentifyResultImpl | class | 24 |
| PresidioFirewall | class | 32 |

### `src/lintel/infrastructure/vault/postgres_vault.py`

| Type | Kind | Line |
|------|------|------|
| PostgresPIIVault | class | 18 |

### `src/lintel/infrastructure/mcp/tool_client.py`

| Type | Kind | Line |
|------|------|------|
| MCPToolClient | class | 18 |

### `src/lintel/infrastructure/repos/github_provider.py`

| Type | Kind | Line |
|------|------|------|
| GitHubRepoProvider | class | 14 |

## Agents & Workflows

### `src/lintel/agents/runtime.py`

| Type | Kind | Line |
|------|------|------|
| AgentRuntime | class | 27 |

### `src/lintel/workflows/nodes/_event_helpers.py`

| Type | Kind | Line |
|------|------|------|
| _AuditStore | Protocol | 13 |

---

**Totals:** ~280 type definitions (65 dataclasses in types.py, 87 event dataclasses, 12 commands, 12 protocols, 27 enums, 7 config classes, 50+ request/response models, 24 Postgres stores, 7 exceptions)
