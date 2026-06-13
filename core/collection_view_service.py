from dataclasses import dataclass

from .collections_manager import (
    CollectionError,
    create_user_collection,
    get_user_collection,
    list_user_collections,
)
from .game_manager import listar_jogos_biblioteca


@dataclass(frozen=True)
class CollectionCardView:
    id: str
    name: str
    game_count: int


@dataclass(frozen=True)
class CollectionsOverviewView:
    title: str
    meta_text: str
    collections: tuple[CollectionCardView, ...]

    @property
    def is_empty(self):
        return not self.collections


@dataclass(frozen=True)
class OpenCollectionView:
    id: str
    name: str
    game_count: int
    game_ids: tuple[str, ...]
    games: tuple
    missing_game_ids: tuple[str, ...]
    meta_text: str

    @property
    def is_empty(self):
        return not self.game_ids


def get_collections_overview(user_id=None):
    collections = tuple(
        CollectionCardView(
            id=collection.id,
            name=collection.name,
            game_count=collection.game_count,
        )
        for collection in list_user_collections(user_id)
    )
    return CollectionsOverviewView(
        title="Coleções",
        meta_text=(
            f"{len(collections)} coleção(ões)"
            if collections
            else "Crie coleções para organizar seus jogos"
        ),
        collections=collections,
    )


def get_open_collection_view(collection_id, user_id=None):
    collection = get_user_collection(collection_id, user_id)
    if not collection:
        return None

    games_by_id = {game.name: game for game in listar_jogos_biblioteca("")}
    games = []
    missing_game_ids = []

    for game_id in collection.game_ids:
        game = games_by_id.get(game_id)
        if game:
            games.append(game)
        else:
            missing_game_ids.append(game_id)

    return OpenCollectionView(
        id=collection.id,
        name=collection.name,
        game_count=collection.game_count,
        game_ids=collection.game_ids,
        games=tuple(games),
        missing_game_ids=tuple(missing_game_ids),
        meta_text=f"{collection.game_count} jogo(s) nesta coleção",
    )


def create_collection(name, user_id=None):
    return create_user_collection(name, user_id)


__all__ = [
    "CollectionError",
    "CollectionCardView",
    "CollectionsOverviewView",
    "OpenCollectionView",
    "create_collection",
    "get_collections_overview",
    "get_open_collection_view",
]
