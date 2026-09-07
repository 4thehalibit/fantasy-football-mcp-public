"""Sleeper-only handlers for MCP tools.

These handlers read exclusively from Sleeper's public API, which requires no
authentication. They are therefore usable without Yahoo Fantasy API access,
unlike the league-scoped tools which need a provisioned Yahoo app.
"""

from typing import Dict, List, Optional

from sleeper_api import sleeper_client

VALID_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DEF"}


def _filter_by_position(players: List[Dict], position: Optional[str]) -> List[Dict]:
    """Filter enriched player dicts by position, tolerating missing values."""
    if not position or position.upper() == "ALL":
        return players
    wanted = position.upper()
    return [p for p in players if (p.get("position") or "").upper() == wanted]


async def handle_ff_sleeper_trending(arguments: Dict) -> Dict:
    """Get players most added or dropped across Sleeper leagues.

    Args:
        arguments: Optional 'add_drop' ("add" or "drop", default "add"),
            'hours' lookback window (default 24), 'limit' (default 25),
            and 'position' filter (QB/RB/WR/TE/K/DEF/all)

    Returns:
        Dict with trending players, or an error dict on failure
    """
    add_drop = str(arguments.get("add_drop", "add")).lower()
    if add_drop not in {"add", "drop"}:
        return {"error": f"add_drop must be 'add' or 'drop', got: {add_drop}"}

    hours = int(arguments.get("hours", 24))
    limit = int(arguments.get("limit", 25))
    position = arguments.get("position")

    # Over-fetch when filtering so the post-filter list can still reach `limit`.
    fetch_limit = limit * 6 if position and position.upper() != "ALL" else limit

    players = await sleeper_client.get_trending_players(
        add_drop=add_drop, hours=hours, limit=fetch_limit
    )
    if not players:
        return {
            "status": "error",
            "message": "Sleeper returned no trending data",
            "source": "Sleeper",
        }

    filtered = _filter_by_position(players, position)[:limit]
    return {
        "status": "success",
        "source": "Sleeper (no authentication required)",
        "add_drop": add_drop,
        "lookback_hours": hours,
        "position_filter": (position or "all").upper(),
        "count": len(filtered),
        "players": filtered,
    }


async def handle_ff_sleeper_rankings(arguments: Dict) -> Dict:
    """Get tiered position rankings from Sleeper's internal search rank.

    Args:
        arguments: Required 'position' (QB/RB/WR/TE/K/DEF), optional
            'limit' (default 25, max 50) and 'week'

    Returns:
        Dict with ranked, tiered players, or an error dict on failure
    """
    position = arguments.get("position")
    if not position:
        return {"error": "position is required (QB, RB, WR, TE, K, or DEF)"}

    position = str(position).upper()
    if position not in VALID_POSITIONS:
        return {
            "error": f"Unsupported position: {position}",
            "valid_positions": sorted(VALID_POSITIONS),
        }

    limit = min(int(arguments.get("limit", 25)), 50)
    week = arguments.get("week")

    rankings = await sleeper_client.get_position_rankings(position, week)
    if not rankings:
        return {
            "status": "error",
            "message": f"Sleeper returned no rankings for {position}",
            "source": "Sleeper",
        }

    return {
        "status": "success",
        "source": "Sleeper (no authentication required)",
        "position": position,
        "week": week,
        "count": len(rankings[:limit]),
        "rankings": rankings[:limit],
    }


async def handle_ff_sleeper_player(arguments: Dict) -> Dict:
    """Look up a single player on Sleeper, with optional expert advice.

    Args:
        arguments: Required 'player_name', optional 'week' and
            'include_advice' (default True)

    Returns:
        Dict with the player card and advice, or an error dict on failure
    """
    player_name = arguments.get("player_name")
    if not player_name:
        return {"error": "player_name is required"}

    week = arguments.get("week")
    include_advice = arguments.get("include_advice", True)

    player = await sleeper_client.get_player_by_name(player_name)
    if not player:
        return {
            "status": "not_found",
            "message": f"No Sleeper player matched: {player_name}",
            "source": "Sleeper",
        }

    result = {
        "status": "success",
        "source": "Sleeper (no authentication required)",
        "query": player_name,
        "player": player,
    }

    if include_advice:
        try:
            result["advice"] = await sleeper_client.get_expert_advice(player_name, week)
        except Exception as exc:  # advice is supplementary - never fail the lookup
            result["advice_error"] = f"{type(exc).__name__}: {exc}"

    return result


async def handle_ff_sleeper_nfl_state(arguments: Dict) -> Dict:
    """Get the current NFL season state (week, season, season type).

    Args:
        arguments: Empty dict (no arguments required)

    Returns:
        Dict with Sleeper's NFL state payload
    """
    state = await sleeper_client.get_nfl_state()
    if not state:
        return {
            "status": "error",
            "message": "Sleeper returned no NFL state",
            "source": "Sleeper",
        }

    return {
        "status": "success",
        "source": "Sleeper (no authentication required)",
        "state": state,
    }
