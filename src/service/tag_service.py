from typing import List, Optional, Dict, Any
from uuid import UUID
from psycopg import AsyncConnection

from src.models.models import Tag
from src.repository.tag import TagRepository
from src.repository.entity_tag import EntityTagRepository

class TagService:
    """Service for managing tags and entity-tag relationships."""
    
    def __init__(self):
        self.tag_repo = TagRepository()
        self.entity_tag_repo = EntityTagRepository()
    
    async def get_tag(self, conn: AsyncConnection, tag_id: str) -> Optional[Tag]:
        """Get a tag by ID."""
        return await self.tag_repo.get_by_id(conn, tag_id)
    
    async def get_tag_by_path(self, conn: AsyncConnection, path: str) -> Optional[Tag]:
        """Get a tag by path."""
        return await self.tag_repo.get_by_path(conn, path)
    
    async def create_tag(self, conn: AsyncConnection, tag: Tag) -> Tag:
        """Create a new tag."""
        return await self.tag_repo.create(conn, tag)
    
    async def update_tag(self, conn: AsyncConnection, tag_id: str, update_data: Dict[str, Any]) -> Optional[Tag]:
        """Update an existing tag."""
        return await self.tag_repo.update(conn, tag_id, update_data)
    
    async def delete_tag(self, conn: AsyncConnection, tag_id: str) -> bool:
        """Delete a tag."""
        return await self.tag_repo.delete(conn, tag_id)
    
    async def get_tag_children(self, conn: AsyncConnection, parent_path: str) -> List[Tag]:
        """Get all direct children of a tag."""
        return await self.tag_repo.get_children(conn, parent_path)
    
    async def get_tag_ancestors(self, conn: AsyncConnection, path: str) -> List[Tag]:
        """Get all ancestors of a tag."""
        return await self.tag_repo.get_ancestors(conn, path)
    
    async def search_tags(self, conn: AsyncConnection, name_pattern: str, limit: int = 20) -> List[Tag]:
        """Search for tags by name pattern."""
        return await self.tag_repo.search_by_name(conn, name_pattern, limit)
    
    # Entity-tag relationship methods
    
    async def add_tag_to_entity(self, conn: AsyncConnection, entity_id: UUID, entity_type: str, tag_id: str) -> bool:
        """Add a tag to an entity."""
        # Verify the tag exists
        tag = await self.tag_repo.get_by_id(conn, tag_id)
        if not tag:
            return False
        
        return await self.entity_tag_repo.add_tag_to_entity(conn, entity_id, entity_type, tag_id)
    
    async def remove_tag_from_entity(self, conn: AsyncConnection, entity_id: UUID, entity_type: str, tag_id: str) -> bool:
        """Remove a tag from an entity."""
        return await self.entity_tag_repo.remove_tag_from_entity(conn, entity_id, entity_type, tag_id)
    
    async def get_entity_tags(self, conn: AsyncConnection, entity_id: UUID, entity_type: str) -> List[Tag]:
        """Get all tags for an entity."""
        return await self.entity_tag_repo.get_entity_tags(conn, entity_id, entity_type)
    
    async def get_entities_with_tag(self, conn: AsyncConnection, tag_id: str, entity_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all entities with a specific tag."""
        return await self.entity_tag_repo.get_entities_with_tag(conn, tag_id, entity_type)
    
    async def get_entities_with_any_tags(self, conn: AsyncConnection, tag_ids: List[str], entity_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all entities that have any of the specified tags."""
        return await self.entity_tag_repo.get_entities_with_any_tags(conn, tag_ids, entity_type)
    
    async def get_entities_with_all_tags(self, conn: AsyncConnection, tag_ids: List[str], entity_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all entities that have all of the specified tags."""
        return await self.entity_tag_repo.get_entities_with_all_tags(conn, tag_ids, entity_type)
