import json
import re
from dataclasses import dataclass
from pathlib import Path

from .storage_manager import ensure_user_storage, get_user_root


class CollectionError(ValueError):
    pass


@dataclass(frozen=True)
class UserCollection:
    id: str
    name: str
    game_ids: tuple[str, ...]

    @property
    def game_count(self):
        return len(self.game_ids)


def _collections_file(user_id=None):
    root = ensure_user_storage(user_id)
    return root / "collections.json"


def _load_store(user_id=None):
    path = _collections_file(user_id)
    if not path.exists():
        return {"schema_version": 1, "collections": []}

    try:
        with path.open("r", encoding="utf-8") as arquivo:
            data = json.load(arquivo)
    except (OSError, json.JSONDecodeError):
        return {"schema_version": 1, "collections": []}

    collections = data.get("collections")
    if not isinstance(collections, list):
        collections = []

    return {"schema_version": 1, "collections": collections}


def _save_store(store, user_id=None):
    path = _collections_file(user_id)
    with path.open("w", encoding="utf-8") as arquivo:
        json.dump(store, arquivo, ensure_ascii=False, indent=2)


def _normalize_collection_name(name):
    name = str(name or "").strip()
    if not name:
        raise CollectionError("Informe o nome da coleção.")
    if len(name) > 60:
        raise CollectionError("Use um nome de coleção mais curto.")
    if any(char in name for char in "\r\n\t"):
        raise CollectionError("O nome da coleção contém caracteres inválidos.")
    return name


def _make_collection_id(name, collections):
    base = re.sub(r"[^a-z0-9_]+", "_", name.lower())
    base = re.sub(r"_+", "_", base).strip("_") or "colecao"
    existing_ids = {str(collection.get("id") or "") for collection in collections}
    collection_id = base
    suffix = 2
    while collection_id in existing_ids:
        collection_id = f"{base}_{suffix}"
        suffix += 1
    return collection_id


def _collection_from_dict(collection):
    game_ids = collection.get("game_ids", [])
    if not isinstance(game_ids, list):
        game_ids = []
    return UserCollection(
        id=str(collection.get("id") or ""),
        name=str(collection.get("name") or "Coleção"),
        game_ids=tuple(str(game_id) for game_id in game_ids if game_id),
    )


def list_user_collections(user_id=None):
    store = _load_store(user_id)
    collections = [
        _collection_from_dict(collection)
        for collection in store["collections"]
        if isinstance(collection, dict) and collection.get("id")
    ]
    return sorted(collections, key=lambda collection: collection.name.lower())


def get_user_collection(collection_id, user_id=None):
    collection_id = str(collection_id or "")
    for collection in list_user_collections(user_id):
        if collection.id == collection_id:
            return collection
    return None


def create_user_collection(name, user_id=None):
    name = _normalize_collection_name(name)
    store = _load_store(user_id)
    collections = store.setdefault("collections", [])

    for collection in collections:
        if not isinstance(collection, dict):
            continue
        if str(collection.get("name") or "").casefold() == name.casefold():
            raise CollectionError("Já existe uma coleção com esse nome.")

    collection = {
        "id": _make_collection_id(name, collections),
        "name": name,
        "game_ids": [],
    }
    collections.append(collection)
    _save_store(store, user_id)
    return _collection_from_dict(collection)


def get_user_collections_file(user_id=None):
    return _collections_file(user_id)
