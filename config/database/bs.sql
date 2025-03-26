create extension vector;
create extension ltree;

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
    id               uuid       not null primary key,
    uri              text       not null unique,
    created_at       timestamp,
    last_accessed_at timestamp,
    extra            jsonb
);

create table root_files
(
    id        uuid         not null primary key,
    root_id   uuid         not null references roots,
    name      varchar(255) not null,
    path      text         not null,
    extension varchar(50),
    mime_type varchar(100),
    size      integer,
    atime     timestamp,
    mtime     timestamp,
    ctime     timestamp,
    extra     jsonb
);

-- Unique index on root_id/path
create unique index uq_root_files_root_id_path on root_files (root_id, path);


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


create table tags (
    id varchar(50) primary key,  -- human-readable string id
    path ltree not null,         -- hierarchical path using ltree
    name varchar(100) not null,  -- display name of the tag
    description text,            -- optional description
    created_at timestamp    not null default current_timestamp,
    updated_at timestamp    not null default current_timestamp,
    constraint valid_path_format check (path::text ~ '^([a-z0-9_]+\.)*[a-z0-9_]+$')  -- ensure path follows ltree format
);

create index tags_path_idx on tags using gist (path);
create index tags_path_idx_btree on tags using btree (path);
