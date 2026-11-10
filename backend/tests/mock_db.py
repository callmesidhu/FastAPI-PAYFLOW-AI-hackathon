"""In-memory async MongoDB mock supporting queries, projections, sorting, and pagination.

Supports:
- Field equality, $regex, $ne, $in, $nin, $lt, $lte, $gt, $gte
- Logical $or and $and
- Dotted-path field access (e.g. "items.name" searches nested list dicts)
- Date/string comparison normalisation (datetime.date vs ISO string)
- update_many for bulk $set operations
"""

import re
from datetime import date
from typing import Any, Dict, List, Optional


def _normalise(v: Any) -> Any:
    """Normalise datetime.date → ISO string for consistent comparisons."""
    if isinstance(v, date):
        return str(v)
    return v


def match_field(doc_val: Any, cond: Any) -> bool:
    """Evaluate MongoDB single-field matching rules."""
    if isinstance(cond, dict):
        if "$regex" in cond:
            pattern = cond["$regex"]
            flags = re.IGNORECASE if cond.get("$options") == "i" else 0
            if doc_val is None:
                return False
            # For list fields (e.g. items), test each element's string representation
            if isinstance(doc_val, list):
                return any(bool(re.search(pattern, str(item), flags)) for item in doc_val)
            return bool(re.search(pattern, str(doc_val), flags))
        if "$ne" in cond:
            return _normalise(doc_val) != _normalise(cond["$ne"])
        if "$in" in cond:
            return _normalise(doc_val) in [_normalise(v) for v in cond["$in"]]
        if "$nin" in cond:
            return _normalise(doc_val) not in [_normalise(v) for v in cond["$nin"]]
        if "$lt" in cond:
            if doc_val is None:
                return False
            return _normalise(doc_val) < _normalise(cond["$lt"])
        if "$lte" in cond:
            if doc_val is None:
                return False
            return _normalise(doc_val) <= _normalise(cond["$lte"])
        if "$gt" in cond:
            if doc_val is None:
                return False
            return _normalise(doc_val) > _normalise(cond["$gt"])
        if "$gte" in cond:
            if doc_val is None:
                return False
            return _normalise(doc_val) >= _normalise(cond["$gte"])
    return _normalise(doc_val) == _normalise(cond)


def _get_nested(doc: Dict[str, Any], path: str) -> Any:
    """Resolve a dotted field path, returning a flat list of values for array fields.

    E.g. "items.name" on a doc with items=[{"name":"A"}, {"name":"B"}]
    returns ["A", "B"].
    """
    parts = path.split(".", 1)
    if len(parts) == 1:
        return doc.get(parts[0])

    head, rest = parts
    sub = doc.get(head)
    if isinstance(sub, list):
        # Collect values from each element
        results = []
        for item in sub:
            if isinstance(item, dict):
                v = _get_nested(item, rest)
                if isinstance(v, list):
                    results.extend(v)
                elif v is not None:
                    results.append(v)
        return results if results else None
    if isinstance(sub, dict):
        return _get_nested(sub, rest)
    return None


def match_document(doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
    """Evaluate full document matching with $or / $and and dotted-path support."""
    for key, val in query.items():
        if key == "$or":
            if not isinstance(val, list):
                return False
            if not any(match_document(doc, sub_q) for sub_q in val):
                return False
            continue
        if key == "$and":
            if not isinstance(val, list):
                return False
            if not all(match_document(doc, sub_q) for sub_q in val):
                return False
            continue

        # Resolve dotted paths (e.g. "items.name")
        doc_val = _get_nested(doc, key) if "." in key else doc.get(key)

        if isinstance(doc_val, list) and isinstance(val, dict) and "$regex" in val:
            # For array fields, check if any element matches the regex
            pattern = val["$regex"]
            flags = re.IGNORECASE if val.get("$options") == "i" else 0
            if not any(bool(re.search(pattern, str(v), flags)) for v in doc_val):
                return False
            continue

        if not match_field(doc_val, val):
            return False
    return True


class MockAsyncCursor:
    """Mock MongoDB async cursor supporting chaining: sort, skip, limit."""

    def __init__(self, items: List[Dict[str, Any]]) -> None:
        self.items = list(items)

    def sort(self, key_or_list: Any, direction: int = 1) -> "MockAsyncCursor":
        # Handle simple string or list of (key, direction) tuples
        if isinstance(key_or_list, list) and key_or_list:
            key, direction = key_or_list[0]
        else:
            key = key_or_list

        reverse = (direction == -1)
        self.items.sort(key=lambda d: str(_normalise(d.get(key, ""))), reverse=reverse)
        return self

    def skip(self, n: int) -> "MockAsyncCursor":
        if n > 0:
            self.items = self.items[n:]
        return self

    def limit(self, n: int) -> "MockAsyncCursor":
        if n >= 0:
            self.items = self.items[:n]
        return self

    def __aiter__(self) -> "MockAsyncCursor":
        self._iter = iter(self.items)
        return self

    async def __anext__(self) -> Dict[str, Any]:
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration

    async def to_list(self, length: Optional[int] = None) -> List[Dict[str, Any]]:
        if length is not None:
            return self.items[:length]
        return list(self.items)


class MockCollection:
    """Mock MongoDB collection implementing common async CRUD operations."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.docs: List[Dict[str, Any]] = []

    async def insert_one(self, doc: Dict[str, Any]) -> Any:
        copied = dict(doc)
        self.docs.append(copied)
        return copied

    async def find_one(self, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        for d in self.docs:
            if match_document(d, query):
                return dict(d)
        return None

    def find(self, query: Dict[str, Any]) -> MockAsyncCursor:
        matched = [dict(d) for d in self.docs if match_document(d, query)]
        return MockAsyncCursor(matched)

    async def count_documents(self, query: Dict[str, Any]) -> int:
        return sum(1 for d in self.docs if match_document(d, query))

    async def replace_one(
        self,
        filter_query: Dict[str, Any],
        replacement: Dict[str, Any],
        upsert: bool = False,
    ) -> Any:
        for idx, d in enumerate(self.docs):
            if match_document(d, filter_query):
                self.docs[idx] = dict(replacement)
                return True
        if upsert:
            self.docs.append(dict(replacement))
            return True
        return False

    async def update_one(self, filter_query: Dict[str, Any], update: Dict[str, Any]) -> Any:
        for d in self.docs:
            if match_document(d, filter_query):
                if "$set" in update:
                    d.update(update["$set"])
                return True
        return False

    async def update_many(self, filter_query: Dict[str, Any], update: Dict[str, Any]) -> Any:
        """Update all matching documents. Returns a result with .modified_count."""
        modified_count = 0
        for d in self.docs:
            if match_document(d, filter_query):
                if "$set" in update:
                    d.update(update["$set"])
                modified_count += 1

        class _UpdateResult:
            def __init__(self, n: int) -> None:
                self.modified_count = n

        return _UpdateResult(modified_count)

    async def delete_one(self, filter_query: Dict[str, Any]) -> Any:
        for idx, d in enumerate(self.docs):
            if match_document(d, filter_query):
                del self.docs[idx]
                return True
        return False


class MockDatabase:
    """In-memory mock database for isolated testing."""

    def __init__(self) -> None:
        self._collections: Dict[str, MockCollection] = {}

    def __getitem__(self, name: str) -> MockCollection:
        if name not in self._collections:
            self._collections[name] = MockCollection(name)
        return self._collections[name]

    def __getattr__(self, name: str) -> MockCollection:
        return self[name]
