#!/usr/bin/env python3
"""Expose the local Qdrant instance via the Model Context Protocol.

This server wraps a handful of frequently used Qdrant operations so Codex (or
any MCP-capable client) can browse collections, run vector searches, and scroll
payloads without invoking the CLI directly. The implementation favours the HTTP
transport that Sinevec already uses (`127.0.0.1:6333`) and keeps the interface
very small on purpose.

Environment variables:
  - `QDRANT_URL` (default `http://127.0.0.1:6333`)
  - `QDRANT_API_KEY` (optional, passed straight to the client)

Example usage (Codex CLI):
  codex mcp call qdrant list-collections
  codex mcp call qdrant scroll-points '{"collection": "knowledgebase", "limit": 5}'
  codex mcp call qdrant search-vector '{"collection": "knowledgebase", "vector": [...], "limit": 3}'
"""

from __future__ import annotations

import os
from functools import wraps
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from mcp.server.fastmcp import FastMCP
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest_models


QDRANT_URL = os.environ.get("QDRANT_URL", "http://127.0.0.1:6333")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY")


def _create_client() -> QdrantClient:
    return QdrantClient(
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY or None,
        prefer_grpc=False,
        timeout=10.0,
    )


client = _create_client()

mcp = FastMCP(
    name="Local Qdrant",
    instructions="Inspect and query the local Qdrant vector store.",
)


def _serialize(item: Any) -> Any:
    if hasattr(item, "model_dump"):
        return item.model_dump(mode="python")
    if hasattr(item, "dict"):
        return item.dict()
    if isinstance(item, (list, tuple)):
        return [_serialize(i) for i in item]
    if isinstance(item, dict):
        return {k: _serialize(v) for k, v in item.items()}
    return item


def _optional_filter(filter_data: Optional[Dict[str, Any]]) -> Optional[rest_models.Filter]:
    if filter_data is None:
        return None
    try:
        return rest_models.Filter.model_validate(filter_data)
    except AttributeError:
        return rest_models.Filter.parse_obj(filter_data)


def _optional_search_params(params: Optional[Dict[str, Any]]) -> Optional[rest_models.SearchParams]:
    if params is None:
        return None
    try:
        return rest_models.SearchParams.model_validate(params)
    except AttributeError:
        return rest_models.SearchParams.parse_obj(params)


def _handle_qdrant_errors(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as exc:  # pylint: disable=broad-except
            raise RuntimeError(f"Qdrant error: {exc}") from exc

    return wrapper


@mcp.tool(name="list-collections", description="List available Qdrant collections")
@_handle_qdrant_errors
def list_collections() -> List[Dict[str, Any]]:
    response = client.get_collections()
    return [_serialize(collection) for collection in response.collections]


@mcp.tool(name="collection-info", description="Fetch metadata for a collection")
@_handle_qdrant_errors
def collection_info(collection: str) -> Dict[str, Any]:
    info = client.get_collection(collection)
    return _serialize(info)


@mcp.tool(
    name="scroll-points",
    description="Page through points in a collection using the Scroll API.",
)
@_handle_qdrant_errors
def scroll_points(
    collection: str,
    limit: int = 20,
    offset: Optional[Dict[str, Any]] = None,
    payload_filter: Optional[Dict[str, Any]] = None,
    with_payload: bool = True,
    with_vectors: bool = False,
) -> Dict[str, Any]:
    q_filter = _optional_filter(payload_filter)
    points, next_offset = client.scroll(
        collection_name=collection,
        limit=limit,
        offset=offset,
        filter=q_filter,
        with_payload=with_payload,
        with_vectors=with_vectors,
    )
    return {
        "points": [_serialize(point) for point in points],
        "next_page_offset": _serialize(next_offset),
    }


@mcp.tool(
    name="search-vector",
    description="Run a vector similarity search within a collection.",
)
@_handle_qdrant_errors
def search_vector(
    collection: str,
    vector: Iterable[float],
    limit: int = 5,
    payload_filter: Optional[Dict[str, Any]] = None,
    with_payload: bool = True,
    with_vectors: bool = False,
    vector_name: Optional[str] = None,
    search_params: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    query_vector = list(vector)
    if not query_vector:
        raise ValueError("vector must contain at least one float")

    q_filter = _optional_filter(payload_filter)
    params = _optional_search_params(search_params)

    results = client.search(
        collection_name=collection,
        query_vector={vector_name: query_vector} if vector_name else query_vector,
        limit=limit,
        filter=q_filter,
        with_payload=with_payload,
        with_vectors=with_vectors,
        search_params=params,
    )
    return [_serialize(match) for match in results]


@mcp.tool(
    name="get-point",
    description="Retrieve one or more points by id.",
)
@_handle_qdrant_errors
def get_point(
    collection: str,
    ids: Iterable[str],
    with_payload: bool = True,
    with_vectors: bool = False,
) -> List[Dict[str, Any]]:
    id_list: List[str] = list(ids)
    if not id_list:
        raise ValueError("ids must contain at least one identifier")
    records = client.retrieve(
        collection_name=collection,
        ids=id_list,
        with_payload=with_payload,
        with_vectors=with_vectors,
    )
    return [_serialize(record) for record in records]


@mcp.tool(name="count-points", description="Count points in a collection (optional filter)")
@_handle_qdrant_errors
def count_points(collection: str, payload_filter: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    q_filter = _optional_filter(payload_filter)
    response = client.count(collection_name=collection, filter=q_filter, exact=True)
    return _serialize(response)


if __name__ == "__main__":
    mcp.run()
