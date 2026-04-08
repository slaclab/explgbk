-- PostgreSQL schema for pief-logdb
-- Auto-generated from SQLModel metadata via backend/scripts/gen_ddl.py
-- DO NOT EDIT MANUALLY — run `make schema` to regenerate.


CREATE TABLE entries (
	id UUID NOT NULL, 
	legacy_id VARCHAR, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	occurred_at TIMESTAMP WITH TIME ZONE, 
	title VARCHAR NOT NULL, 
	content TEXT NOT NULL, 
	content_type VARCHAR NOT NULL, 
	author_id UUID NOT NULL, 
	version INTEGER NOT NULL, 
	retracted_by UUID, 
	retracted_time TIMESTAMP WITH TIME ZONE, 
	root_id UUID, 
	run_id UUID, 
	shift_id UUID, 
	PRIMARY KEY (id), 
	FOREIGN KEY(root_id) REFERENCES entries (id)
);
CREATE INDEX ix_entries_legacy_id ON entries (legacy_id);

CREATE TABLE instruments (
	id UUID NOT NULL, 
	legacy_id VARCHAR, 
	meta JSONB NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);
CREATE INDEX ix_instruments_legacy_id ON instruments (legacy_id);

CREATE TABLE logbooks (
	id UUID NOT NULL, 
	type VARCHAR NOT NULL, 
	name VARCHAR NOT NULL, 
	description TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	UNIQUE (name)
);

CREATE TABLE tags (
	id UUID NOT NULL, 
	name VARCHAR NOT NULL, 
	description VARCHAR, 
	color VARCHAR, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	UNIQUE (name)
);

CREATE TABLE users (
	id UUID NOT NULL, 
	username VARCHAR NOT NULL, 
	display_name VARCHAR, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_users_username ON users (username);

CREATE TABLE attachments (
	id UUID NOT NULL, 
	entry_id UUID NOT NULL, 
	legacy_id VARCHAR, 
	name VARCHAR, 
	description TEXT, 
	filename VARCHAR NOT NULL, 
	mime_type VARCHAR NOT NULL, 
	size_bytes INTEGER NOT NULL, 
	uri VARCHAR NOT NULL, 
	preview_uri VARCHAR, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(entry_id) REFERENCES entries (id)
);
CREATE INDEX ix_attachments_entry_id ON attachments (entry_id);
CREATE INDEX ix_attachments_legacy_id ON attachments (legacy_id);

CREATE TABLE entry_revisions (
	id UUID NOT NULL, 
	legacy_id VARCHAR, 
	entry_id UUID NOT NULL, 
	version INTEGER NOT NULL, 
	revised_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	revised_by UUID NOT NULL, 
	title VARCHAR NOT NULL, 
	content TEXT NOT NULL, 
	content_type VARCHAR NOT NULL, 
	occurred_at TIMESTAMP WITH TIME ZONE, 
	tag_ids UUID[] NOT NULL, 
	attachment_ids UUID[] NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_entry_revision_version UNIQUE (entry_id, version), 
	FOREIGN KEY(entry_id) REFERENCES entries (id)
);
CREATE INDEX ix_entry_revisions_legacy_id ON entry_revisions (legacy_id);
CREATE INDEX ix_entry_revisions_entry_id ON entry_revisions (entry_id);

CREATE TABLE entry_tags (
	entry_id UUID NOT NULL, 
	tag_id UUID NOT NULL, 
	PRIMARY KEY (entry_id, tag_id), 
	FOREIGN KEY(entry_id) REFERENCES entries (id), 
	FOREIGN KEY(tag_id) REFERENCES tags (id)
);

CREATE TABLE experiments (
	id UUID NOT NULL, 
	legacy_id VARCHAR, 
	name VARCHAR NOT NULL, 
	description TEXT, 
	start_time TIMESTAMP WITH TIME ZONE NOT NULL, 
	end_time TIMESTAMP WITH TIME ZONE, 
	instrument_id UUID, 
	proposal_id UUID, 
	logbook_id UUID, 
	meta JSONB NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	UNIQUE (name), 
	FOREIGN KEY(instrument_id) REFERENCES instruments (id), 
	FOREIGN KEY(logbook_id) REFERENCES logbooks (id)
);
CREATE INDEX ix_experiments_legacy_id ON experiments (legacy_id);

CREATE TABLE external_links (
	id UUID NOT NULL, 
	entry_id UUID NOT NULL, 
	system VARCHAR NOT NULL, 
	uri VARCHAR NOT NULL, 
	meta JSONB, 
	PRIMARY KEY (id), 
	FOREIGN KEY(entry_id) REFERENCES entries (id)
);
CREATE INDEX ix_external_links_entry_id ON external_links (entry_id);

CREATE TABLE logbook_entries (
	entry_id UUID NOT NULL, 
	logbook_id UUID NOT NULL, 
	PRIMARY KEY (entry_id, logbook_id), 
	FOREIGN KEY(entry_id) REFERENCES entries (id), 
	FOREIGN KEY(logbook_id) REFERENCES logbooks (id)
);
