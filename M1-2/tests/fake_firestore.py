"""A deliberately small Firestore double, used only by offline tests.

It validates read-before-write ordering and atomically applies staged writes.
It is not a Firestore emulator and does not prove SDK/RPC/cloud behavior.
"""

from copy import deepcopy


class Snapshot:
    def __init__(self, document_id, value):
        self.id = document_id
        self._value = deepcopy(value)
        self.exists = value is not None

    def to_dict(self):
        return deepcopy(self._value)


class Document:
    def __init__(self, client, collection, document_id):
        self.client, self.collection, self.id = client, collection, document_id

    def get(self, transaction=None, **_kwargs):
        if self.client.fail_reads:
            raise RuntimeError("private-sdk-error-do-not-echo")
        if transaction is not None and transaction.writes:
            raise AssertionError("Firestore reads must happen before writes")
        return Snapshot(self.id, self.client.data.get(self.collection, {}).get(self.id))


class Query:
    def __init__(self, client, collection, filters=(), projection=None):
        self.client, self.collection, self.filters = client, collection, filters
        self.projection = projection

    def where(self, *, filter):
        assert filter.op_string == "=="
        return Query(self.client, self.collection, (*self.filters, filter), self.projection)

    def select(self, field_paths):
        return Query(self.client, self.collection, self.filters, tuple(field_paths))

    def stream(self, transaction=None, **_kwargs):
        if self.client.fail_reads:
            raise RuntimeError("private-sdk-error-do-not-echo")
        if transaction is not None and transaction.writes:
            raise AssertionError("Firestore reads must happen before writes")
        self.client.query_projections.append((self.collection, self.projection))
        for key, value in list(self.client.data.get(self.collection, {}).items()):
            if all(value.get(item.field_path) == item.value for item in self.filters):
                selected = value if self.projection is None else {field: value[field] for field in self.projection if field in value}
                yield Snapshot(key, selected)


class Collection(Query):
    def document(self, document_id):
        return Document(self.client, self.collection, document_id)


class FakeFirestore:
    def __init__(self):
        self.data = {}
        self.fail_reads = False
        self.fail_commit = False
        self.query_projections = []

    def collection(self, name):
        return Collection(self, name)


class Transaction:
    def __init__(self):
        self.writes = []

    def create(self, ref, data):
        self.writes.append(("create", ref, deepcopy(data), False))

    def set(self, ref, data, merge=False):
        self.writes.append(("set", ref, deepcopy(data), merge))

    def delete(self, ref):
        self.writes.append(("delete", ref, None, False))


def run_transaction(client, action):
    transaction = Transaction()
    result = action(transaction)
    if client.fail_commit:
        raise RuntimeError("private-commit-error-do-not-echo")
    updated = deepcopy(client.data)
    for operation, ref, value, merge in transaction.writes:
        collection = updated.setdefault(ref.collection, {})
        if operation == "create":
            assert ref.id not in collection
            collection[ref.id] = value
        elif operation == "set":
            collection[ref.id] = {**collection.get(ref.id, {}), **value} if merge else value
        else:
            collection.pop(ref.id, None)
    client.data = updated
    return result
