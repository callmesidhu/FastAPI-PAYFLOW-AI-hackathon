"""In-memory async MongoDB mock supporting queries, projections, sorting, and pagination."""

import re
from typing import Any, Dict, List, Optional


def match_field(doc_val: Any, cond: Any) -> bool:
    """Evaluate MongoDB field matching rules."""
    if isinstance(cond, dict):
        if "$regex" in cond:
            pattern = cond["$regex"]
            flags = re.IGNORECASE if cond.get("$options") == "i" else 0
            if doc_val is None:
                return False
            return bool(re.search(pattern, str(doc_val), flags))
        if "$ne" in cond:
            return doc_val != cond["$ne"]
        if "$in" in cond:
            return doc_val in cond["$in"]
        if "$nin" in cond:
            return doc_val not in cond["$nin"]
    return doc_val == cond


def match_document(doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
    """Evaluate full document matching with $or support."""
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

        if not match_field(doc.get(key), val):
            return False
    return True


class MockAsyncCursor:
    """Mock MongoDB async cursor supporting chaining: sort, skip, limit."""

    def __init__(self, items: List[Dict[str, Any]]) -> None:
        self.items = list(items)

    def sort(self, key_or_list: Any, direction: int = 1) -> "MockAsyncCursor":
        # Handle simple string or list of (key, direction)
        if isinstance(key_or_list, list) and key_or_list:
            key, direction = key_or_list[0]
        else:
            key = key_or_list

        reverse = (direction == -1)
        self.items.sort(key=lambda d: str(d.get(key, "")), reverse=reverse)
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

    async def replace_one(self, filter_query: Dict[str, Any], replacement: Dict[str, Any]) -> Any:
        for idx, d in enumerate(self.docs):
            if match_document(d, filter_query):
                self.docs[idx] = dict(replacement)
                return True
        return False

    async def update_one(self, filter_query: Dict[str, Any], update: Dict[str, Any]) -> Any:
        for d in self.docs:
            if match_document(d, filter_query):
                if "$set" in update:
                    d.update(update["$set"])
                return True
        return False

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
