
import logging
import re
import shlex

from collections import defaultdict

from .metadata import VALID_TAG_RE, VALID_KEY_RE, FIXED_METADATA_D, FIXED_METADATA_KEYS

class SQLQuery:
    def __init__(self, tables, where_clause, parameters):
        self.tables = tables
        self.where_clause = where_clause
        self.parameters = parameters

NULL_SQL_QUERY = SQLQuery([], "", [])
NOTHING_SQL_QUERY = SQLQuery([], "FALSE", [])
BASE_SQL_QUERY = SQLQuery(["items item"], "", [])

DANGEROUS_CHARS_RE = re.compile(r"[\"'\\]")
NEED_QUOTES_RE = re.compile(r"[ \\\"\t]")
NEED_ESCAPING_RE = re.compile(r"[\"\\]")

logger = logging.getLogger("search")

def quote(data, force=False):
    """Quote string using ""

    shlex.quote() won't help, as it uses '' which behaves a bit differently in
    shell syntax than we need in our queries."""
    if not force and not NEED_QUOTES_RE.search(data):
        return data
    return '"' + NEED_ESCAPING_RE.sub(r"\\\0", data) + '"'

class SearchCondition:
    applied_in_group = False
    @classmethod
    def from_string(cls, query):
        raise NotImplementedError
    def to_string(self):
        return "".join(self.to_strings())
    def to_strings(self):
        raise NotImplementedError
    def get_sql_query(self, cond_number):
        raise NotImplementedError
    @classmethod
    def get_sql_group_query(cls, conditions):
        raise NotImplementedError

class SearchQuery:
    cond_types = []
    def __init__(self, conditions):
        self.conditions = conditions
    def __str__(self):
        return self.as_string()
    @classmethod
    def add_condition_type(cls, cond_class):
        cls.cond_types.append(cond_class)
    @classmethod
    def from_string(cls, query):
        try:
            parts = shlex.split(query)
        except ValueError as err:
            logger.warning("Could not parse %r: %s", query, err)
            # make up something usable
            query = DANGEROUS_CHARS_RE.sub("", query)
            parts = query.split()
        logger.debug("spit query: %r", parts)
        conditions = []
        for part in parts:
            for cond_type in cls.cond_types:
                try:
                    cond = cond_type.from_string(part)
                    conditions.append(cond)
                    break
                except ValueError as err:
                    logging.debug("skipping part: %s", err)
                    continue
            else:
                logging.warning("Cannot understand query %r", part)
                continue
        return cls(conditions)
    def add_conditions(self, conditions):
        self.conditions += list(conditions)
    def as_string(self):
        conds = []
        for cond in self.conditions:
            parts = []
            for part in condition.as_strings():
                parts.append(quote(part))
            conds.append("".join(cond_s))
        return " ".join(conds)
    def as_sql(self, columns=None, order_by="item.name", limit=100):
        logger.debug("Translating %r to SQL query", self.conditions)
        if columns:
            column_names = ["item." + name if "." not in name else name
                            for name in columns]
            column_list = "{}".format(", ".join(column_names))
        else:
            column_list = "item.*"
        queries = []
        grouped_conds = defaultdict(list)
        cond_nr = 0
        for cond in self.conditions:
            if cond.applied_in_group:
                grouped_conds[type(cond)].append(cond)
            else:
                query = cond.get_sql_query(cond_nr)
                cond_nr += 1
                queries.append(query)
        for cond_type, conds in grouped_conds.items():
            query = cond_type.get_sql_group_query(conds, cond_nr)
            cond_nr += 1
            queries.append(query)
        logger.debug("query components: %r", queries)
        tables = ["items item"]
        where = []
        params = []
        for query in queries:
            tables += query.tables
            if query.where_clause:
                where.append(query.where_clause)
            params += query.parameters
        joins = tables[:1]
        for table in tables[1:]:
            if "JOIN" in table:
                joins.append(" " + table)
            else:
                joins.append(", " + table)
        sql_query = "SELECT {} FROM {}".format(column_list, "".join(joins))
        if where:
            sql_query += " WHERE {}".format(" AND ".join(where))
        if order_by:
            sql_query += " ORDER BY {}".format(order_by)
        if limit:
            sql_query += " LIMIT {}".format(limit)
        logger.debug("result query: %r, %r", sql_query, params)
        return sql_query, params

class TagQuery(SearchCondition):
    applied_in_group = True
    def __init__(self, tag_name, exclude=False):
        self.tag_name = tag_name
        self.exclude = exclude
    def __repr__(self):
        return "<TagQuery {}{!r}>".format("exclude " if self.exclude else "",
                                        self.tag_name)
    @classmethod
    def from_string(cls, query):
        if len(query) < 2:
            raise ValueError("Not a tag query: %r - too short" % (query,))
        if query.startswith("+"):
            exclude = False
        elif query.startswith("-"):
            exclude = True
        else:
            raise ValueError("Not a tag query: %r - bad prefix" % (query,))
        if query[1:] == "/":
            return cls("/", exclude)
        elif not VALID_TAG_RE.match(query[1:]):
            raise ValueError("Not a tag query: %r - bad tag name" % (query,))
        return cls(query[1:], exclude)

    @classmethod
    def get_sql_group_query(cls, tag_queries, cond_number):
        included = set()
        excluded = set()
        include_all = False
        for tag_query in tag_queries:
            if tag_query.tag_name == "/":
                if tag_query.exclude:
                    return NOTHING_SQL_QUERY
                else:
                    include_all = True
                continue
            if tag_query.exclude:
                excluded.add(tag_query.tag_name)
            else:
                included.add(tag_query.tag_name)
        if include_all:
            included = set()
        if not included and not excluded:
            return NULL_SQL_QUERY

        where = ["itag.item_id = item.id"]
        params = []

        if included:
            where.append("itag.tag_id IN (SELECT id FROM tags WHERE name IN ({}))"
                         .format(",".join(["?"] * len(included))))
            params += list(included)
        if excluded:
            where.append("itag.tag_id NOT IN (SELECT id FROM tags WHERE tag_name IN ({}))"
                         .format(",".join(["?"] * len(included))))
            params += list(excluded)
        return SQLQuery(["item_tags itag"], " AND ".join(where), params)

SearchQuery.add_condition_type(TagQuery)

class MetadataQuery(SearchCondition):
    def __init__(self, key, value, oper="="):
        self.key = key.lower()
        self.value = value
        self.oper = oper
    def __repr__(self):
        return "<MetadataQuery {!r} {} {!r}>".format(self.key, self.oper, self.value)
    @classmethod
    def from_string(cls, query):
        for oper in ("=", "==", "<", ">", "<=", ">=", "!=", "<>"):
            if oper in query:
                break
        else:
            raise ValueError("Not a metadata query: %r - operator missing" % (query,))
        key, value = query.split(oper, 1)
        key = key.strip()

        if key.startswith("_"):
            if key not in FIXED_METADATA_KEYS:
                raise ValueError("Not a metadata query: %r - unknonw key" % (query,))
        elif not VALID_KEY_RE.match(key):
            raise ValueError("Not a metadata query: %r - invalid key" % (query,))

        return cls(key, value, oper)

    def get_sql_query(self, cond_number):
        params = []
        where = []

        if self.key.startswith("_"):
            fixed_key = self.key[1:]
            custom_key = None
        elif self.key in FIXED_METADATA_D:
            fixed_key = self.key
            custom_key = self.key
        else:
            fixed_key = None
            custom_key = self.key

        if fixed_key:
            where.append("item.{} = ?".format(fixed_key))
            params.append(self.value)

        if custom_key:
            where.append("(icv{i}.item_id = item.id"
                         " AND ck{i}.id = icv{i}.key_id"
                         " AND ck{i}.name = ?"
                         " AND icv{i}.value = ?)"
                         .format(i=cond_number))
            params += [self.key, self.value]
            tables = ["LEFT JOIN item_custom_values icv{i}".format(i=cond_number),
                    "LEFT JOIN custom_keys ck{i}".format(i=cond_number)]
            return SQLQuery(tables, "(" + " OR ".join(where) + ")", params)
        else:
            return SQLQuery(None, where[0], params)

SearchQuery.add_condition_type(MetadataQuery)

class MiscQuery(SearchCondition):
    applied_in_group = True
    def __init__(self, query):
        self.query = query
    def __repr__(self):
        return "<MiscQuery {!r}>".format(self.query)
    @classmethod
    def from_string(cls, query):
        return cls(query)
    @classmethod
    def get_sql_group_query(cls, queries, cond_number):
        query_string = []
        for part in queries:
            query_string.append(quote(part.query))
        return SQLQuery(["fts fts"],
                        "item.id = fts.docid AND fts.content MATCH ?",
                        [" ".join(query_string)])

SearchQuery.add_condition_type(MiscQuery)
