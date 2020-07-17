

class SampleMetadata:
    def __init__(self, data=None):
        if data is not None:
            self.data = dict(data)
        else:
            self.data = {}
    @classmethod
    def from_file_info(cls, file_info):
        return cls(file_info)
    def __iter__(self):
        return iter(self.data)
    def __repr__(self):
        return "SampleMetadata({!r})".format(self.data)
    def __len__(self):
        return len(self.data)
    def get(self, key, default=None):
        return self.data.get(key, default)
    def __getitem__(self, key):
        return self.data[key]
    def __contains__(self, key):
        return key in self.data
