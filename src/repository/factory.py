from typing import Type, Dict, Optional

from src.models.models import Session, Message, Tag, Blob, Stash
from src.repository.base import BaseRepository
from src.repository.session import SessionRepository
from src.repository.message import MessageRepository
from src.repository.tag import TagRepository
from src.repository.blob import BlobRepository
from src.repository.stash import StashRepository


class RepositoryFactory:
    """Factory for creating repository instances."""
    
    _instances: Dict[Type, BaseRepository] = {}
    
    @classmethod
    def get_repository(cls, model_class):
        """Get or create a repository instance for a model class."""
        if model_class not in cls._instances:
            # Check if there's a specialized repository for this model
            repo_class = cls._get_specialized_repository(model_class)
            if repo_class:
                cls._instances[model_class] = repo_class()
            else:
                # Fall back to base repository
                cls._instances[model_class] = BaseRepository(model_class)
        
        return cls._instances[model_class]
    
    @staticmethod
    def _get_specialized_repository(model_class) -> Optional[Type[BaseRepository]]:
        """Get the specialized repository class for a model class if it exists."""
        # Map model classes to their specialized repository classes
        repository_map = {
            Session: SessionRepository,
            Message: MessageRepository,
            Tag: TagRepository,
            Blob: BlobRepository,
            Stash: StashRepository,
        }
        return repository_map.get(model_class)
