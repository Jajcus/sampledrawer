
CREATE TABLE db_meta (
        id INTEGER PRIMARY KEY,
        version INTEGER
);

CREATE TABLE items (
	id INTEGER PRIMARY KEY,
	sha256 TEXT,
	path TEXT,
	source TEXT,
	name TEXT,
	format TEXT,
	format_subtype TEXT,
	sample_rate INTEGER,
	duration FLOAT
);

CREATE TABLE tags (
	id INTEGER PRIMARY KEY,
	name TEXT NOT NULL UNIQUE,
	is_category BOOLEAN DEFAULT FALSE NOT NULL,
	parent INTEGER REFERENCES categories(id)
);

CREATE TABLE library (
	id INTEGER PRIMARY KEY,
	item_id INTEGER NOT NULL REFERENCES item(id)
);

CREATE TABLE scratchpads (
	id INTEGER PRIMARY KEY,
	scratchpad_name TEXT UNIQUE NOT NULL
);

CREATE TABLE scratchpad_items (
	id INTEGER PRIMARY KEY,
	scratchpad_id INTEGER NOT NULL REFERENCES scratchpads(id)
);
