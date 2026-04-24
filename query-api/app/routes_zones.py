"""Zones endpoint — currently just hot-cells heatmap data."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from .auth import ApiKey
from .deps import require_api_key
from .hot_cells import LATEST_KEY, cells_to_features

router = APIRouter()


@router.get("/zones/hot")
async def hot_zones(
    request: Request,
    limit: int = Query(400, ge=1, le=5000),
    _key: ApiKey = Depends(require_api_key),
) -> dict:
    """Return a GeoJSON FeatureCollection of HEALPix cells with the most
    satellites active in the latest 1-minute window (populated by Flink)."""
    r = request.app.state.redis
    latest = await r.get(LATEST_KEY)
    if not latest:
        return {"type": "FeatureCollection", "features": [], "window_end_ms": None}
    key = f"sky:hot:{latest}"
    raw = await r.zrevrange(key, 0, limit - 1, withscores=True)
    cells: list[tuple[int, int]] = [(int(c), int(s)) for c, s in raw]
    features = cells_to_features(cells)
    return {
        "type": "FeatureCollection",
        "features": features,
        "window_end_ms": int(latest),
        "count": len(features),
    }
