create extension vector;
create extension ltree;

-- Create a function for updating timestamps
CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

create table sessions
(
    id            uuid      not null primary key,
    description   text,
    goal          text,
    created_at    timestamp    not null default current_timestamp,
    updated_at    timestamp    not null default current_timestamp,
    template      jsonb,
    status        varchar(50),
    current_state varchar(100),
    workflow_data jsonb,
    error         text
);

-- Apply timestamp trigger to sessions table
CREATE TRIGGER update_timestamp_sessions
BEFORE UPDATE ON sessions
FOR EACH ROW EXECUTE FUNCTION update_timestamp();

create table messages
(
    id         uuid         not null primary key,
    parent_id  uuid references messages,
    session_id uuid         not null references sessions,
    role       varchar(50)  not null,
    model      varchar(100),
    text       text         not null,
    status     varchar(50),
    mime_type  varchar(100),
    timestamp  timestamp,
    extra      jsonb
);

create table roots
(
    uri              text       not null primary key,
    created_at       timestamp  not null default current_timestamp,
    extra            jsonb
);

create table root_files
(
    root_uri   text         not null references roots(uri),
    path       text         not null,
    name       varchar(255) not null,
    extension  varchar(50),
    mime_type  varchar(100),
    size       integer,
    atime      timestamp,
    mtime      timestamp,
    ctime      timestamp,
    extra      jsonb,
    primary key (root_uri, path)
);


create table blobs
(
    id           uuid         not null primary key,
    name         varchar(255) not null,
    description  text,
    content_type varchar(100) not null,
    content_url  text         not null,
    byte_size    bigint,
    sha256       varchar(64),
    created_at   timestamp    not null default current_timestamp,
    updated_at   timestamp    not null default current_timestamp,
    metadata     jsonb
);

-- Apply timestamp trigger to blobs table
CREATE TRIGGER update_timestamp_blobs
BEFORE UPDATE ON blobs
FOR EACH ROW EXECUTE FUNCTION update_timestamp();


create table tags (
    id varchar(50) primary key,  -- human-readable string id
    path ltree not null,         -- hierarchical path using ltree
    name varchar(100) not null,  -- display name of the tag
    description text,            -- optional description
    created_at timestamp    not null default current_timestamp,
    updated_at timestamp    not null default current_timestamp,
    constraint valid_path_format check (path::text ~ '^([a-z0-9_]+\.)*[a-z0-9_]+$')  -- ensure path follows ltree format
);

-- Apply timestamp trigger to tags table
CREATE TRIGGER update_timestamp_tags
BEFORE UPDATE ON tags
FOR EACH ROW EXECUTE FUNCTION update_timestamp();

create index tags_path_idx on tags using gist (path);
create index tags_path_idx_btree on tags using btree (path);

create table stashes (
    id uuid not null primary key,
    name varchar(255) not null,
    description text,
    items jsonb not null default '[]'::jsonb,  -- Array of StashItem objects
    created_at timestamp not null default current_timestamp,
    updated_at timestamp not null default current_timestamp,
    metadata jsonb
);

-- Apply timestamp trigger to stashes table
CREATE TRIGGER update_timestamp_stashes
BEFORE UPDATE ON stashes
FOR EACH ROW EXECUTE FUNCTION update_timestamp();

create index stashes_name_idx on stashes (name);


-- create entity_tags junction table
create table if not exists entity_tags (
    entity_id uuid not null,
    entity_type varchar(50) not null,
    tag_id varchar(255) not null,
    created_at timestamp with time zone default now(),
    primary key (entity_id, entity_type, tag_id),
    foreign key (tag_id) references tags(id) on delete cascade
);

-- create index on entity_id and entity_type for faster lookups
create index if not exists idx_entity_tags_entity on entity_tags(entity_id, entity_type);
-- create index on tag_id for faster lookups
create index if not exists idx_entity_tags_tag on entity_tags(tag_id);

-- create entity_stashes junction table
create table if not exists entity_stashes (
    entity_id uuid not null,
    entity_type varchar(50) not null,
    stash_id uuid not null,
    created_at timestamp with time zone default now(),
    primary key (entity_id, entity_type, stash_id),
    foreign key (stash_id) references stashes(id) on delete cascade
);

-- create index on entity_id and entity_type for faster lookups
create index if not exists idx_entity_stashes_entity on entity_stashes(entity_id, entity_type);
-- create index on stash_id for faster lookups
create index if not exists idx_entity_stashes_stash on entity_stashes(stash_id);

-- add comment to explain the tables
comment on table entity_tags is 'junction table for associating tags with various entity types';
comment on table entity_stashes is 'junction table for associating stashes with various entity types';
