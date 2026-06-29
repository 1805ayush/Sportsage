from enum import StrEnum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class MatchStatus(StrEnum):
    SCHEDULED  = "SCHEDULED"
    IN_PLAY    = "IN_PLAY"
    PAUSED     = "PAUSED"       # half-time
    FINISHED   = "FINISHED"
    POSTPONED  = "POSTPONED"
    CANCELLED  = "CANCELLED"
    SUSPENDED  = "SUSPENDED"

class Competition(BaseModel):
    id: str
    name: str
    code: str
    country: Optional[str] =None

class Team(BaseModel):
    id: str
    name: str
    short_name: Optional[str] = None
    tla: Optional[str] = None    

class Match(BaseModel):
    id:          str
    competition: str                    # competition code — PL, WC, CL …
    season:      int
    matchday:    Optional[int]    = None
    status:      MatchStatus
    utc_date:    datetime
    home_team:   Team
    away_team:   Team
    home_score:  Optional[int]    = None
    away_score:  Optional[int]    = None
    ht_home:     Optional[int]    = None   # half-time scores
    ht_away:     Optional[int]    = None
    minute:      Optional[int]    = None   # live match minute
    stage:       Optional[str]    = None   # GROUP_STAGE, ROUND_OF_16 …
    group:       Optional[str]    = None   # Group A, B … (World Cup)

class Standing(BaseModel):
    competition:    str
    season:         int
    position:       int
    team:           Team
    played:         int
    won:            int
    drawn:          int
    lost:           int
    goals_for:      int
    goals_against:  int
    goal_diff:      int
    points:         int
    stage:          Optional[str] = None
    group:          Optional[str] = None 

class Scorer(BaseModel):
    competition:  str
    season:       int
    player_name:  str
    team:         Optional[Team] = None
    goals:        int
    assists:      Optional[int]  = None
    penalties:    Optional[int]  = None    

class Player(BaseModel):
    id:       Optional[str] = None
    name:     str
    position: Optional[str] = None
    number:   Optional[int] = None

class MatchLineup(BaseModel):
    match_id:       str
    home_lineup:    list[Player] = []
    away_lineup:    list[Player] = []
    home_formation: Optional[str] = None
    away_formation: Optional[str] = None

class MatchStats(BaseModel):
    match_id: str
    home_xg:  Optional[float] = None
    away_xg:  Optional[float] = None

 
class LiveScore(BaseModel):
    match_id:         str
    competition:      str
    competition_name: str
    home_team:        str
    away_team:        str
    home_score:       Optional[int]=None
    away_score:       Optional[int]=None
    status:           MatchStatus
    minute:           Optional[int] = None
    stage:            Optional[str] = None
    utc_date:         str               # ISO string — datetime not Redis-serializable
    source:           str               # "espn" | "wc2026" | "football_data"
 
    def to_redis_dict(self) -> dict[str, str]:
        """Flat string dict for XADD — Redis requires all values as strings."""
        return {
            k: str(v) if v is not None else ""
            for k, v in self.model_dump().items()
        }
 
    @classmethod
    def from_redis_dict(cls, data: dict[bytes, bytes]) -> "LiveScore":
        """Parse an XREAD response entry back into a LiveScore."""
        decoded = {k.decode(): v.decode() for k, v in data.items()}
        # empty string → None for optional fields
        for field in ("minute", "stage","home_score","away_score"):
            if decoded.get(field) == "":
                decoded[field] = None
        return cls(**decoded)            
