# This file is kept for backward compatibility
# It re-exports all models from the models module

from src.models.models import (
    Base,
    Message,
    Session,
    Flow,
    Artifact,
    FlowTemplate,
    ScratchPad,
    artifact_scratchpad,
    POSTGRES_INDEXES_NAMING_CONVENTION
)

# Re-export all models
__all__ = [
    'Base',
    'Message',
    'Session',
    'Flow',
    'Artifact',
    'FlowTemplate',
    'ScratchPad',
    'artifact_scratchpad',
    'POSTGRES_INDEXES_NAMING_CONVENTION'
]
