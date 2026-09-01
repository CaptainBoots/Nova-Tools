"""
core/media_registry.py
────────────────────────
Canonical list of known media players/sources, in default priority
order. This is the single source of truth for two things that used to
be two separate hardcoded structures in monitors/media.py (a
PRIORITY_ORDER list and a raw-id -> label mapping dict) — they drifted
out of sync with each other easily, so both are now derived from this
one list instead.

Each entry is (id, label, match_keys):
  id         stable identifier used for priority ordering/persistence
             (cfg["media_priority_order"]) and as the row in Settings'
             reorderable list. Never shown to the person directly.
  label      human-readable display name — shown in the OSC output AND
             as that row's text in the priority list.
  match_keys one or more lowercase substrings checked against the raw
             session/player id (Windows AUMID, or the Linux/MPRIS
             player name playerctl reports). Most players only need
             one, but some genuinely report different raw ids across
             versions/builds — e.g. Firefox and Chrome both have an
             alternate SMTC AUMID depending on Windows/browser version.
             These must stay grouped under ONE id/label rather than
             becoming separate rows: they're the same real player, and
             splitting them would mean reordering one variant in
             Settings silently does nothing for the other variant,
             with no indication why — that's exactly the duplicate-row
             bug this structure exists to prevent.

Order here is the DEFAULT priority (dedicated apps > browsers > video
players > communication apps > native OS players) — Settings lets the
user drag this into whatever order they actually want; their saved
order is layered on top of this list at runtime (see
monitors/media.py's set_priority_order()).

A note on browser-embedded web playback (Spotify Web, YouTube Music
web, etc.): Windows SMTC and Linux MPRIS both report the *browser* as
the source unless the site is installed as its own PWA (Chrome/Edge
"Install as app") — a regular browser tab can't be told apart from any
other tab in the same browser this way. That's expected, not a bug;
the "youtube"/"soundcloud"/etc. entries below exist for PWA installs
and dedicated desktop apps, not for matching arbitrary tabs. The
Spotify entry is the one exception — see monitors/media.py's Spotify
Web API integration, which identifies Spotify directly instead of
guessing from a browser AUMID.
"""

# fmt: off
PLAYER_REGISTRY: list[tuple[str, str, list[str]]] = [
    # ── 1. Dedicated music/streaming apps + PWAs ─────────────────────────────
    ("spotify",        "Spotify",            ["spotify"]),
    ("applemusic",     "Apple Music",        ["applemusic"]),
    ("itunes",         "iTunes",             ["itunes"]),
    ("tidal",          "Tidal",              ["tidal"]),
    ("deezer",         "Deezer",             ["deezer"]),
    ("youtubemusic",   "YouTube Music",      ["youtubemusic"]),
    ("amazonmusic",    "Amazon Music",       ["amazonmusic"]),
    ("pandora",        "Pandora",            ["pandora"]),
    ("soundcloud",     "SoundCloud",         ["soundcloud"]),
    ("napster",        "Napster",            ["napster"]),
    ("qobuz",          "Qobuz",              ["qobuz"]),
    ("bandcamp",       "Bandcamp",           ["bandcamp"]),
    ("audible",        "Audible",            ["audible"]),
    ("foobar2000",     "foobar2000",         ["foobar2000"]),
    ("winamp",         "Winamp",             ["winamp"]),
    ("musicbee",       "MusicBee",           ["musicbee"]),
    ("aimp",           "AIMP",               ["aimp"]),
    ("mediamonkey",    "MediaMonkey",        ["mediamonkey"]),
    ("jriver",         "JRiver Media Center", ["jriver"]),
    ("roon",           "Roon",               ["roon"]),
    ("audirvana",      "Audirvana",          ["audirvana"]),
    ("clementine",     "Clementine",         ["clementine"]),
    ("strawberry",     "Strawberry",         ["strawberry"]),
    ("rhythmbox",      "Rhythmbox",          ["rhythmbox"]),
    ("audacious",      "Audacious",          ["audacious"]),
    ("deadbeef",       "DeaDBeeF",           ["deadbeef"]),
    ("cmus",           "cmus",               ["cmus"]),
    ("lollypop",       "Lollypop",           ["lollypop"]),
    ("elisa",          "Elisa",              ["elisa"]),
    ("amarok",         "Amarok",             ["amarok"]),
    ("banshee",        "Banshee",            ["banshee"]),

    # ── 2. Web browsers ───────────────────────────────────────────────────────
    # Firefox and Chrome each have a second AUMID some Windows/browser
    # versions report instead of the obvious one — both keys must stay
    # under the SAME id so reordering moves both variants together.
    ("firefox",        "Firefox",  ["firefox", "308046b0"]),
    ("chrome",         "Chrome",   ["chrome", "googlechrome"]),
    ("edge",           "Edge",     ["msedge", "edge"]),
    ("brave",          "Brave",    ["brave"]),
    ("opera",          "Opera",    ["opera"]),
    ("vivaldi",        "Vivaldi",  ["vivaldi"]),
    ("waterfox",       "Waterfox", ["waterfox"]),
    ("librewolf",      "LibreWolf", ["librewolf"]),
    ("chromium",       "Chromium", ["chromium"]),

    # ── 3. Video players + streaming video ──────────────────────────────────
    ("vlc",            "VLC",           ["vlc"]),
    ("mpc-hc",         "MPC-HC",        ["mpc-hc", "mpchc"]),
    ("mpv",            "mpv",           ["mpv"]),
    ("potplayer",      "PotPlayer",     ["potplayer"]),
    ("kmplayer",       "KMPlayer",      ["kmplayer"]),
    ("gomplayer",      "GOM Player",    ["gomplayer"]),
    ("kodi",           "Kodi",          ["kodi"]),
    ("plex",           "Plex",          ["plex"]),
    ("emby",           "Emby",          ["emby"]),
    ("jellyfin",       "Jellyfin",      ["jellyfin"]),
    ("netflix",        "Netflix",       ["netflix"]),
    ("disneyplus",     "Disney+",       ["disneyplus"]),
    ("hulu",           "Hulu",          ["hulu"]),
    ("hbomax",         "Max",           ["hbomax"]),
    ("paramountplus",  "Paramount+",    ["paramountplus"]),
    ("primevideo",     "Prime Video",   ["primevideo"]),
    ("twitch",         "Twitch",        ["twitch"]),
    ("youtube",        "YouTube",       ["youtube"]),

    # Just for fun — e621 has no desktop app, MPRIS, or SMTC integration of
    # any kind, so this will essentially never actually match anything for
    # real. Left in as an easter egg rather than functional detection.
    ("e621",           "e621",          ["e621"]),

    # ── 4. Communication utilities ───────────────────────────────────────────
    ("discord",        "Discord",  ["discord"]),
    ("telegram",       "Telegram", ["telegram"]),
    ("whatsapp",       "WhatsApp", ["whatsapp"]),
    ("zoom",           "Zoom",     ["zoom"]),
    ("teams",          "Teams",    ["teams"]),

    # ── 5. Native OS players ──────────────────────────────────────────────────
    ("zune",           "Windows Media Player", ["zune"]),
    ("winmusic",       "Media Player",         ["microsoft.windows.music"]),
    ("zunevideo",      "Movies & TV",          ["microsoft.zunevideo"]),
    ("groovemusic",    "Groove Music",         ["groovemusic"]),
]
# fmt: on


def default_order() -> list[str]:
    """Registry order, as a flat list of ids — the out-of-the-box
    priority order before any user customization in Settings."""
    return [entry_id for entry_id, _label, _keys in PLAYER_REGISTRY]


def labels() -> dict[str, str]:
    """id -> display label, for both source_name() and the Settings
    reorderable list."""
    return {entry_id: label for entry_id, label, _keys in PLAYER_REGISTRY}


def label_for(entry_id: str) -> str:
    return labels().get(entry_id, entry_id)


def id_for_raw(raw_id: str) -> str | None:
    """Given a raw AUMID/MPRIS player-name substring, returns which
    registry id it belongs to (checking every match_key in every
    group), or None if nothing matches."""
    if not raw_id:
        return None
    raw_lower = raw_id.lower()
    for entry_id, _label, match_keys in PLAYER_REGISTRY:
        for key in match_keys:
            if key in raw_lower:
                return entry_id
    return None