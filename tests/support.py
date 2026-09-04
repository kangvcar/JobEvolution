from collections import defaultdict


class MemoryRedis:
    """Small Redis fake shared by collector tests."""

    def __init__(self):
        self._sets = defaultdict(set)
        self._hashes = defaultdict(dict)
        self._streams = defaultdict(list)
        self._seq = 0

    def sismember(self, key: str, value: str) -> bool:
        return value in self._sets.get(key, set())

    def sadd(self, key: str, *values: str) -> int:
        bucket = self._sets[key]
        added = 0
        for value in values:
            if value not in bucket:
                bucket.add(value)
                added += 1
        return added

    def srem(self, key: str, *values: str) -> int:
        bucket = self._sets.get(key)
        if not bucket:
            return 0
        removed = 0
        for value in values:
            if value in bucket:
                bucket.remove(value)
                removed += 1
        return removed

    def xadd(self, name: str, fields: dict, id: str = "*") -> str:
        self._seq += 1
        entry_id = f"0-{self._seq}" if id == "*" else id
        self._streams[name].append((entry_id, {str(k): str(v) for k, v in fields.items()}))
        return entry_id

    def xrange(self, name: str, min: str = "-", max: str = "+", count: int | None = None):
        items = list(self._streams.get(name, []))
        return items[:count] if count is not None else items

    def hget(self, key: str, field: str):
        return self._hashes.get(key, {}).get(field)

    def hset(self, key: str, field: str, value: str) -> int:
        self._hashes[key][field] = value
        return 1

    def xrevrange(self, name: str, max: str = "+", min: str = "-", count: int | None = None):
        items = list(reversed(self._streams.get(name, [])))
        return items[:count] if count is not None else items

    def xread(self, streams: dict, block: int | None = None, count: int | None = None):
        out = []
        for name, last in streams.items():
            items = []
            last_seq = -1 if last in {"0-0", "0", "-", None} else int(str(last).split("-")[-1])
            if last == "$":
                continue
            for eid, fields in self._streams.get(name, []):
                if int(str(eid).split("-")[-1]) > last_seq:
                    items.append((eid, fields))
            if count is not None:
                items = items[:count]
            if items:
                out.append((name, items))
        return out
