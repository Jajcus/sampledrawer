
CREATE TABLE db_meta (
        id INTEGER PRIMARY KEY,
        version INTEGER
);

CREATE TABLE scratchpads (
	id INTEGER PRIMARY KEY,
	scratchpad_name TEXT UNIQUE NOT NULL
);

CREATE TABLE items (
	id INTEGER PRIMARY KEY,
	scratchpad_id INTEGER REFERENCES scratchpads(id), -- NULL - in library
	md5 TEXT,
	path TEXT,
	source TEXT,
	name TEXT,
	format TEXT,
	format_subtype TEXT,
	sample_rate INTEGER,
	channels INTEGER,
	duration FLOAT,
        peak_level FLOAT
);

CREATE TABLE tags (
	id INTEGER PRIMARY KEY,
	name TEXT NOT NULL UNIQUE
);
CREATE TABLE item_tags (
	id INTEGER PRIMARY KEY,
	item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
	tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
        UNIQUE (item_id, tag_id)
);

CREATE TABLE custom_keys (
	id INTEGER PRIMARY KEY,
	name TEXT NOT NULL UNIQUE
);
CREATE TABLE item_custom_values (
	id INTEGER PRIMARY KEY,
	item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
	key_id INTEGER NOT NULL REFERENCES custom_keys(id) ON DELETE CASCADE,
	value TEXT,
	UNIQUE (item_id, key_id)
);

CREATE VIRTUAL TABLE item_index USING fts4(metadata_blob);
