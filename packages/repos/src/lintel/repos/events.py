"""Repository domain events."""

from __future__ import annotations

from dataclasses import dataclass

from lintel.contracts.events import EventEnvelope, register_events


@dataclass(frozen=True)
class RepositoryRegistered(EventEnvelope):
    event_type: str = "RepositoryRegistered"


@dataclass(frozen=True)
class RepositoryUpdated(EventEnvelope):
    event_type: str = "RepositoryUpdated"


@dataclass(frozen=True)
class RepositoryRemoved(EventEnvelope):
    event_type: str = "RepositoryRemoved"


@dataclass(frozen=True)
class RepoCloned(EventEnvelope):
    event_type: str = "RepoCloned"


@dataclass(frozen=True)
class BranchCreated(EventEnvelope):
    event_type: str = "BranchCreated"


@dataclass(frozen=True)
class CommitPushed(EventEnvelope):
    event_type: str = "CommitPushed"


@dataclass(frozen=True)
class PRCreated(EventEnvelope):
    event_type: str = "PRCreated"


@dataclass(frozen=True)
class PRCommentAdded(EventEnvelope):
    event_type: str = "PRCommentAdded"


register_events(
    RepositoryRegistered,
    RepositoryUpdated,
    RepositoryRemoved,
    RepoCloned,
    BranchCreated,
    CommitPushed,
    PRCreated,
    PRCommentAdded,
)
