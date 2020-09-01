
CREATE TABLE db_meta (
        id INTEGER PRIMARY KEY,
        version TEXT
);

CREATE TABLE workplaces (
	id INTEGER PRIMARY KEY,
	name TEXT UNIQUE NOT NULL
);

CREATE TABLE items (
	id INTEGER PRIMARY KEY,
	workplace_id INTEGER REFERENCES workplaces(id), -- NULL - in library
	md5 TEXT,
	path TEXT,
	source TEXT,
	name TEXT COLLATE NOCASE,
	format TEXT,
	format_subtype TEXT,
	sample_rate INTEGER,
	channels INTEGER,
	duration FLOAT,
        peak_level FLOAT
);

CREATE TABLE tags (
	id INTEGER PRIMARY KEY,
	name TEXT COLLATE NOCASE NOT NULL UNIQUE,
	item_count INTEGER DEFAULT 0
);
INSERT INTO tags(id, name) VALUES (0, "/"); -- pseudo-tag to count all library items

CREATE TABLE item_tags (
	id INTEGER PRIMARY KEY,
	item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
	tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
        UNIQUE (item_id, tag_id)
);

CREATE TABLE custom_keys (
	id INTEGER PRIMARY KEY,
	name TEXT COLLATE NOCASE NOT NULL UNIQUE
);
CREATE TABLE item_custom_values (
	id INTEGER PRIMARY KEY,
	item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
	key_id INTEGER NOT NULL REFERENCES custom_keys(id) ON DELETE CASCADE,
	value TEXT COLLATE NOCASE,
	UNIQUE (item_id, key_id)
);

CREATE VIRTUAL TABLE fts USING fts4(tokenize=unicode61 "tokenchars=~" "separators=_");


CREATE TRIGGER item_tags_insert_update_tag_count AFTER INSERT ON item_tags
BEGIN
	UPDATE tags SET item_count = tags.item_count + 1
		WHERE tags.id = new.tag_id
		AND (SELECT workplace_id FROM items WHERE id=new.item_id LIMIT 1) IS NULL;
END;

CREATE TRIGGER item_tags_delete_update_tag_count AFTER DELETE ON item_tags
BEGIN
	UPDATE tags SET item_count = tags.item_count - 1
		WHERE tags.id = old.tag_id
		AND (SELECT workplace_id FROM items WHERE id=old.item_id LIMIT 1) IS NULL;
END;

CREATE TRIGGER items_insert_update_tag_count AFTER INSERT ON items
BEGIN
	UPDATE tags SET item_count = tags.item_count + 1
		WHERE tags.id = 0 AND new.workplace_id IS NULL;
END;

CREATE TRIGGER items_delete_update_tag_count AFTER DELETE ON items
BEGIN
	UPDATE tags SET item_count = tags.item_count - 1
		WHERE tags.id = 0 AND old.workplace_id IS NULL;
END;

CREATE TRIGGER items_update_update_tag_count AFTER UPDATE ON items
BEGIN
	UPDATE tags SET item_count = tags.item_count + 1
		WHERE old.workplace_id IS NOT NULL
		AND new.workplace_id IS NULL
		AND (
			tags.id IN (SELECT tag_id FROM item_tags WHERE item_id = new.id)
			OR tags.id = 0
	        );

	UPDATE tags SET item_count = tags.item_count - 1
		WHERE old.workplace_id IS NULL
		AND new.workplace_id IS NOT NULL
		AND (
			tags.id IN (SELECT tag_id FROM item_tags WHERE item_id = old.id)
			OR tags.id = 0
		);
END;
