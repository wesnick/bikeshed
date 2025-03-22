create table sessions
(
    id            uuid      not null primary key,
    description   text,
    goal          text,
    created_at    timestamp,
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

