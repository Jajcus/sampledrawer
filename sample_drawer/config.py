
import copy
import json

DEFAULT_IMPORT_RULES = [
        ("_path", r"^(.*/)?([^/]*?)(\.[^/.]*)?$", {"_name": "{2}"}),
        ("_auto_category", r"^/.*$", {"_tags": "{_tags} {0}"}),
        ]

DEFAULT_CONFIG = {
        "rewrite_rules": {
            "default": {
                "name": "Name from filename, tags from folder",
                "rules": DEFAULT_IMPORT_RULES,
                },
            }
        }

class Config:
    def __init__(self):
        self.config = copy.deepcopy(DEFAULT_CONFIG)
    def __getitem__(self, key):
        try:
            return self.config[key]
        except KeyError:
            self.config[key] = copy.deepcopy(DEFAULT_CONFIG[key])
            return self.config[key]
