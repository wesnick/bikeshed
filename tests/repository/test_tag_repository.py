import pytest
from uuid import uuid4
from datetime import datetime

from psycopg import AsyncConnection

from src.models.models import Tag
from src.repository.tag import TagRepository

pytestmark = pytest.mark.asyncio


@pytest.fixture
def tag_repo() -> TagRepository:
    return TagRepository()


def _unique_id(prefix: str) -> str:
    """Generates a unique ID string for tests."""
    return f"{prefix}_{uuid4().hex[:8]}"


@pytest.fixture
def sample_tag_data() -> dict:
    # Use a unique ID for each test run potentially
    tag_id = _unique_id("test_tag")
    # Make path unique as well to avoid collisions in tests like get_by_path
    tag_path = f"test.tag.{tag_id}"
    return {
        "id": tag_id,
        "path": tag_path,
        "name": "Test Tag",
        "description": "A tag for testing",
    }

async def test_create_tag(db_conn_clean: AsyncConnection, tag_repo: TagRepository, sample_tag_data: dict):
    tag = Tag(**sample_tag_data)
    created_tag = await tag_repo.create(db_conn_clean, tag)

    assert created_tag is not None
    assert created_tag.id == sample_tag_data["id"]
    assert created_tag.path == sample_tag_data["path"]
    assert created_tag.name == sample_tag_data["name"]
    assert created_tag.description == sample_tag_data["description"]
    assert isinstance(created_tag.created_at, datetime)
    assert isinstance(created_tag.updated_at, datetime)


async def test_get_tag_by_id(db_conn_clean: AsyncConnection, tag_repo: TagRepository, sample_tag_data: dict):
    tag = Tag(**sample_tag_data)
    created_tag = await tag_repo.create(db_conn_clean, tag)

    # Note: Tag uses string ID, not UUID
    fetched_tag = await tag_repo.get_by_id(db_conn_clean, created_tag.id)

    assert fetched_tag is not None
    assert fetched_tag.id == created_tag.id
    assert fetched_tag.name == created_tag.name


async def test_get_tag_by_id_not_found(db_conn_clean: AsyncConnection, tag_repo: TagRepository):
    non_existent_id = f"non_existent_{uuid4().hex[:8]}"
    fetched_tag = await tag_repo.get_by_id(db_conn_clean, non_existent_id)
    assert fetched_tag is None


async def test_get_all_tags(db_conn_clean: AsyncConnection, tag_repo: TagRepository, sample_tag_data: dict):
    tag1_data = {**sample_tag_data, "id": f"tag1_{uuid4().hex[:8]}", "path": "test.tag1", "name": "Tag 1"}
    tag2_data = {**sample_tag_data, "id": f"tag2_{uuid4().hex[:8]}", "path": "test.tag2", "name": "Tag 2"}
    tag1 = Tag(**tag1_data)
    tag2 = Tag(**tag2_data)
    await tag_repo.create(db_conn_clean, tag1)
    await tag_repo.create(db_conn_clean, tag2)

    all_tags = await tag_repo.get_all(db_conn_clean, limit=10)

    assert len(all_tags) == 2
    tag_names = {t.name for t in all_tags}
    assert "Tag 1" in tag_names
    assert "Tag 2" in tag_names


async def test_update_tag(db_conn_clean: AsyncConnection, tag_repo: TagRepository, sample_tag_data: dict):
    tag = Tag(**sample_tag_data)
    created_tag = await tag_repo.create(db_conn_clean, tag)

    update_data = {"name": "Updated Tag Name", "description": "Updated description"}
    # Note: Tag uses string ID, not UUID
    updated_tag = await tag_repo.update(db_conn_clean, created_tag.id, update_data)

    assert updated_tag is not None
    assert updated_tag.id == created_tag.id
    assert updated_tag.name == "Updated Tag Name"
    assert updated_tag.description == "Updated description"
    assert updated_tag.path == created_tag.path # Path shouldn't change on simple update
    assert updated_tag.updated_at > created_tag.updated_at


async def test_update_tag_not_found(db_conn_clean: AsyncConnection, tag_repo: TagRepository):
    non_existent_id = f"non_existent_{uuid4().hex[:8]}"
    update_data = {"name": "updated_name"}
    updated_tag = await tag_repo.update(db_conn_clean, non_existent_id, update_data)
    assert updated_tag is None


async def test_delete_tag(db_conn_clean: AsyncConnection, tag_repo: TagRepository, sample_tag_data: dict):
    tag = Tag(**sample_tag_data)
    created_tag = await tag_repo.create(db_conn_clean, tag)

    # Note: Tag uses string ID, not UUID
    deleted = await tag_repo.delete(db_conn_clean, created_tag.id)
    assert deleted is True

    fetched_tag = await tag_repo.get_by_id(db_conn_clean, created_tag.id)
    assert fetched_tag is None


async def test_delete_tag_not_found(db_conn_clean: AsyncConnection, tag_repo: TagRepository):
    non_existent_id = f"non_existent_{uuid4().hex[:8]}"
    deleted = await tag_repo.delete(db_conn_clean, non_existent_id)
    assert deleted is False


async def test_filter_tags(db_conn_clean: AsyncConnection, tag_repo: TagRepository, sample_tag_data: dict):
    tag1_data = {**sample_tag_data, "id": f"filter1_{uuid4().hex[:8]}", "path": "filter.test1", "name": "Filter Test One"}
    tag2_data = {**sample_tag_data, "id": f"filter2_{uuid4().hex[:8]}", "path": "filter.test2", "name": "Filter Test Two"}
    tag1 = Tag(**tag1_data)
    tag2 = Tag(**tag2_data)
    await tag_repo.create(db_conn_clean, tag1)
    await tag_repo.create(db_conn_clean, tag2)

    filtered_tags = await tag_repo.filter(db_conn_clean, {"name": "Filter Test Two"})

    assert len(filtered_tags) == 1
    assert filtered_tags[0].id == tag2.id
    assert filtered_tags[0].name == "Filter Test Two"


async def test_get_tag_by_path(db_conn_clean: AsyncConnection, tag_repo: TagRepository, sample_tag_data: dict):
    tag = Tag(**sample_tag_data)
    await tag_repo.create(db_conn_clean, tag)

    fetched_tag = await tag_repo.get_by_path(db_conn_clean, sample_tag_data["path"])

    assert fetched_tag is not None
    assert fetched_tag.id == tag.id
    assert fetched_tag.path == sample_tag_data["path"]


async def test_get_tag_by_path_not_found(db_conn_clean: AsyncConnection, tag_repo: TagRepository):
    fetched_tag = await tag_repo.get_by_path(db_conn_clean, "non.existent.path")
    assert fetched_tag is None


async def test_get_tag_children(db_conn_clean: AsyncConnection, tag_repo: TagRepository):
    p_id = _unique_id("parent")
    c1_id = _unique_id("child1")
    c2_id = _unique_id("child2")
    gc_id = _unique_id("grandchild")
    o_id = _unique_id("other")

    p_path = p_id
    c1_path = f"{p_path}.{c1_id}"
    c2_path = f"{p_path}.{c2_id}"
    gc_path = f"{c1_path}.{gc_id}"
    o_path = o_id

    parent = Tag(id=p_id, path=p_path, name="Parent")
    child1 = Tag(id=c1_id, path=c1_path, name="Child 1")
    child2 = Tag(id=c2_id, path=c2_path, name="Child 2")
    grandchild = Tag(id=gc_id, path=gc_path, name="Grandchild")
    other = Tag(id=o_id, path=o_path, name="Other")

    await tag_repo.create(db_conn_clean, parent)
    await tag_repo.create(db_conn_clean, child1)
    await tag_repo.create(db_conn_clean, child2)
    await tag_repo.create(db_conn_clean, grandchild)
    await tag_repo.create(db_conn_clean, other)

    children = await tag_repo.get_children(db_conn_clean, p_path)

    assert len(children) == 2
    child_ids = {c.id for c in children}
    assert c1_id in child_ids
    assert c2_id in child_ids


async def test_get_tag_children_no_children(db_conn_clean: AsyncConnection, tag_repo: TagRepository):
    p_id = _unique_id("parent_nochild")
    p_path = p_id
    parent = Tag(id=p_id, path=p_path, name="Parent No Children")
    await tag_repo.create(db_conn_clean, parent)

    children = await tag_repo.get_children(db_conn_clean, p_path)
    assert len(children) == 0


async def test_get_tag_ancestors(db_conn_clean: AsyncConnection, tag_repo: TagRepository):
    r_id = _unique_id("root")
    l1_id = _unique_id("level1")
    l2_id = _unique_id("level2")
    o_id = _unique_id("other_anc")

    r_path = r_id
    l1_path = f"{r_path}.{l1_id}"
    l2_path = f"{l1_path}.{l2_id}"
    o_path = o_id

    root = Tag(id=r_id, path=r_path, name="Root")
    level1 = Tag(id=l1_id, path=l1_path, name="Level 1")
    level2 = Tag(id=l2_id, path=l2_path, name="Level 2")
    other = Tag(id=o_id, path=o_path, name="Other Anc")

    await tag_repo.create(db_conn_clean, root)
    await tag_repo.create(db_conn_clean, level1)
    await tag_repo.create(db_conn_clean, level2)
    await tag_repo.create(db_conn_clean, other)

    ancestors = await tag_repo.get_ancestors(db_conn_clean, l2_path)

    assert len(ancestors) == 2
    ancestor_ids = {a.id for a in ancestors}
    assert r_id in ancestor_ids
    assert l1_id in ancestor_ids


async def test_get_tag_ancestors_no_ancestors(db_conn_clean: AsyncConnection, tag_repo: TagRepository):
    r_id = _unique_id("root_noanc")
    r_path = r_id
    root = Tag(id=r_id, path=r_path, name="Root No Ancestors")
    await tag_repo.create(db_conn_clean, root)

    ancestors = await tag_repo.get_ancestors(db_conn_clean, r_path)
    assert len(ancestors) == 0


async def test_search_tag_by_name(db_conn_clean: AsyncConnection, tag_repo: TagRepository):
    s1_id = _unique_id("search1")
    s2_id = _unique_id("search2")
    s3_id = _unique_id("search3")

    tag1 = Tag(id=s1_id, path=f"search.{s1_id}", name="Searchable Tag One")
    tag2 = Tag(id=s2_id, path=f"search.{s2_id}", name="Another Searchable Tag")
    tag3 = Tag(id=s3_id, path=f"search.{s3_id}", name="Completely Different")

    await tag_repo.create(db_conn_clean, tag1)
    await tag_repo.create(db_conn_clean, tag2)
    await tag_repo.create(db_conn_clean, tag3)

    results = await tag_repo.search_by_name(db_conn_clean, "Searchable")

    assert len(results) == 2
    result_ids = {r.id for r in results}
    assert s1_id in result_ids
    assert s2_id in result_ids

    results_case_insensitive = await tag_repo.search_by_name(db_conn_clean, "searchable tag")
    assert len(results_case_insensitive) == 2

    results_partial = await tag_repo.search_by_name(db_conn_clean, "Tag")
    assert len(results_partial) == 2 # Matches "Tag One" and "Tag"

    results_specific = await tag_repo.search_by_name(db_conn_clean, "Completely Different")
    assert len(results_specific) == 1
    assert results_specific[0].id == s3_id


async def test_search_tag_by_name_no_match(db_conn_clean: AsyncConnection, tag_repo: TagRepository):
    s1_id = _unique_id("search_nomatch")
    tag1 = Tag(id=s1_id, path=f"search.{s1_id}", name="Searchable Tag No Match")
    await tag_repo.create(db_conn_clean, tag1)

    results = await tag_repo.search_by_name(db_conn_clean, "NonExistent")
    assert len(results) == 0
