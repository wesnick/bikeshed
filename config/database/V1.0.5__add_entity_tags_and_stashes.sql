-- Create entity_tags junction table
CREATE TABLE IF NOT EXISTS entity_tags (
    entity_id UUID NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    tag_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (entity_id, entity_type, tag_id),
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

-- Create index on entity_id and entity_type for faster lookups
CREATE INDEX IF NOT EXISTS idx_entity_tags_entity ON entity_tags(entity_id, entity_type);
-- Create index on tag_id for faster lookups
CREATE INDEX IF NOT EXISTS idx_entity_tags_tag ON entity_tags(tag_id);

-- Create entity_stashes junction table
CREATE TABLE IF NOT EXISTS entity_stashes (
    entity_id UUID NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    stash_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (entity_id, entity_type, stash_id),
    FOREIGN KEY (stash_id) REFERENCES stashes(id) ON DELETE CASCADE
);

-- Create index on entity_id and entity_type for faster lookups
CREATE INDEX IF NOT EXISTS idx_entity_stashes_entity ON entity_stashes(entity_id, entity_type);
-- Create index on stash_id for faster lookups
CREATE INDEX IF NOT EXISTS idx_entity_stashes_stash ON entity_stashes(stash_id);

-- Add comment to explain the tables
COMMENT ON TABLE entity_tags IS 'Junction table for associating tags with various entity types';
COMMENT ON TABLE entity_stashes IS 'Junction table for associating stashes with various entity types';
