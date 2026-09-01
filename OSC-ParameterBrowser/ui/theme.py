"""
ui/theme.py
───────────
Colour definitions. The active palette is selected by colour_mode,
which is set at startup based on the saved config.

Also provides the Qt-specific pieces used across the app: qss() builds a
global stylesheet from the active palette, qt_font() resolves the theme
font, and StripeBackground paints the diagonal flag-stripe backgrounds
(this replaced the old Tk-canvas draw_stripes() when the UI moved to Qt).
"""

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QColor, QPolygonF, QFont, QFontDatabase
from PySide6.QtWidgets import QWidget, QLabel

colour_mode = "new"

FONT = "Consolas"
TITLE_PREFIX = "◈"

THEMES: dict[str, dict] = {
    "dark": {
        "BG":      "#0f0f13",
        "PANEL":   "#17171f",
        "BORDER":  "#2a2a38",
        "ACCENT":  "#7c5cfc",
        "ACCENT2": "#a78bfa",
        "TAB":     "#4ade80",
        "TEXT":    "#e2e0f0",
        "TEXT2":   "#E0E0E0",
        "SUBTEXT": "#7e7b9a",
        "GREEN":   "#4ade80",
        "RED":     "#f87171",
        "YELLOW":  "#facc15",
        "CYAN":    "#67e8f9",
        "ORANGE":  "#fb923c",
        "STRIPE_COLOURS": None,
    },
    "rich_purple": {
        "BG":      "#0f0f13",
        "PANEL":   "#1f102a",
        "BORDER":  "#2a2a38",
        "ACCENT":  "#9D00FF",
        "ACCENT2": "#b44bff",
        "TAB":     "#4ade80",
        "TEXT":    "#e2e0f0",
        "TEXT2":   "#E0E0E0",
        "SUBTEXT": "#7e7b9a",
        "GREEN":   "#4ade80",
        "RED":     "#f87171",
        "YELLOW":  "#facc15",
        "CYAN":    "#67e8f9",
        "ORANGE":  "#fb923c",
        "STRIPE_COLOURS": None,
    },
    "dark_sand": {
        "BG":      "#1C1D26",
        "PANEL":   "#1f232d",
        "BORDER":  "#353333",
        "ACCENT":  "#FFAC8B",
        "ACCENT2": "#FFC695",
        "TAB":     "#FFC695",
        "TEXT":    "#F5EFE9",
        "TEXT2":   "#E3D8D0",
        "SUBTEXT": "#AE9281",
        "GREEN":   "#4ade80",
        "RED":     "#f87171",
        "YELLOW":  "#facc15",
        "CYAN":    "#67e8f9",
        "ORANGE":  "#FFAC8B",
        "STRIPE_COLOURS": None,
    },
    "absolute_zero": {
        "BG":      "#000D21",
        "PANEL":   "#002154",
        "BORDER":  "#003487",
        "ACCENT":  "#005CED",
        "ACCENT2": "#5496FF",
        "TAB":     "#2177FF",
        "TEXT":    "#EAF3FF",
        "TEXT2":   "#D6E8FF",
        "SUBTEXT": "#A8C4F2",
        "GREEN":   "#4ade80",
        "RED":     "#f87171",
        "YELLOW":  "#facc15",
        "CYAN":    "#67e8f9",
        "ORANGE":  "#fb923c",
        "STRIPE_COLOURS": None,
    },
    "light_purple": {
        "BG":      "#F6E6FA",
        "PANEL":   "#ffffff",
        "BORDER":  "#DDCAE3",
        "ACCENT":  "#9D00FF",
        "ACCENT2": "#b44bff",
        "TAB":     "#000000",
        "TEXT":    "#1a1829",
        "TEXT2":   "#1a1829",
        "SUBTEXT": "#1a1829",
        "GREEN":   "#4ade80",
        "RED":     "#f87171",
        "YELLOW":  "#facc15",
        "CYAN":    "#67e8f9",
        "ORANGE":  "#fb923c",
        "STRIPE_COLOURS": None,
    },
    "light_sand": {
        "BG":      "#fdfbf7",
        "PANEL":   "#f4f1ea",
        "BORDER":  "#e4dfd3",
        "ACCENT":  "#2b5c43",
        "ACCENT2": "#3d7a5a",
        "TAB":     "#000000",
        "TEXT":    "#1c1b18",
        "TEXT2":   "#383630",
        "SUBTEXT": "#706e64",
        "GREEN":   "#15803d",
        "RED":     "#b91c1c",
        "YELLOW":  "#b45309",
        "CYAN":    "#0369a1",
        "ORANGE":  "#c2410c",
        "STRIPE_COLOURS": None,
    },
    "mint": {
        "BG":      "#F5FFFA",
        "PANEL":   "#FFFFFF",
        "BORDER":  "#D6F0E4",
        "ACCENT":  "#2EC4B6",
        "ACCENT2": "#6EE7D8",
        "TAB":     "#1F2937",
        "TEXT":    "#1A2A2A",
        "TEXT2":   "#334155",
        "SUBTEXT": "#64748B",
        "GREEN":   "#22C55E",
        "RED":     "#EF4444",
        "YELLOW":  "#EAB308",
        "CYAN":    "#06B6D4",
        "ORANGE":  "#F97316",
        "STRIPE_COLOURS": None,
    },
    "dark_mint": {
        "BG":      "#0F1C18",
        "PANEL":   "#163129",
        "BORDER":  "#295247",
        "ACCENT":  "#2EC4B6",
        "ACCENT2": "#6EE7D8",
        "TAB":     "#6EE7D8",
        "TEXT":    "#E8FFF9",
        "TEXT2":   "#D3F5EE",
        "SUBTEXT": "#8AB5AB",
        "GREEN":   "#4ADE80",
        "RED":     "#F87171",
        "YELLOW":  "#FACC15",
        "CYAN":    "#67E8F9",
        "ORANGE":  "#FB923C",
        "STRIPE_COLOURS": None,
    },
    "dark_red": {
        "BG":      "#1A0B0B",
        "PANEL":   "#2C1111",
        "BORDER":  "#512121",
        "ACCENT":  "#DC2626",
        "ACCENT2": "#F87171",
        "TAB":     "#F87171",
        "TEXT":    "#FFF1F1",
        "TEXT2":   "#F8DADA",
        "SUBTEXT": "#B48D8D",
        "GREEN":   "#4ADE80",
        "RED":     "#F87171",
        "YELLOW":  "#FACC15",
        "CYAN":    "#67E8F9",
        "ORANGE":  "#FB923C",
        "STRIPE_COLOURS": None,
    },
    "light_red": {
        "BG":      "#FFF5F5",
        "PANEL":   "#FFFFFF",
        "BORDER":  "#F4CACA",
        "ACCENT":  "#DC2626",
        "ACCENT2": "#F87171",
        "TAB":     "#000000",
        "TEXT":    "#2A1111",
        "TEXT2":   "#472020",
        "SUBTEXT": "#735353",
        "GREEN":   "#16A34A",
        "RED":     "#DC2626",
        "YELLOW":  "#CA8A04",
        "CYAN":    "#0284C7",
        "ORANGE":  "#EA580C",
        "STRIPE_COLOURS": None,
    },
    "light_blue": {
        "BG":      "#F2F9FF",
        "PANEL":   "#FFFFFF",
        "BORDER":  "#D2E8F8",
        "ACCENT":  "#3B82F6",
        "ACCENT2": "#60A5FA",
        "TAB":     "#000000",
        "TEXT":    "#172033",
        "TEXT2":   "#2E4468",
        "SUBTEXT": "#6A82A8",
        "GREEN":   "#22C55E",
        "RED":     "#EF4444",
        "YELLOW":  "#EAB308",
        "CYAN":    "#06B6D4",
        "ORANGE":  "#F97316",
        "STRIPE_COLOURS": None,
    },
    "dark_rainbow": {
        "BG":      "#1A1A1A",
        "PANEL":   "#252525",
        "BORDER":  "#444444",
        "ACCENT":  "#E40303",
        "ACCENT2": "#FF8C00",
        "TAB":     "#732982",
        "TEXT":    "#FFFFFF",
        "TEXT2":   "#F0F0F0",
        "SUBTEXT": "#BBBBBB",
        "GREEN":   "#008026",
        "RED":     "#E40303",
        "YELLOW":  "#FFED00",
        "CYAN":    "#004DFF",
        "ORANGE":  "#FF8C00",
        "STRIPE_COLOURS": ["#FF0000", "#FF0700", "#FF0F00", "#FF1600", "#FF1E00", "#FF2600", "#FF2D00", "#FF3500",
                           "#FF3D00", "#FF4400", "#FF4C00", "#FF5400", "#FF5B00", "#FF6300", "#FF6B00", "#FF7200",
                           "#FF7A00", "#FF8200", "#FF8900", "#FF9100", "#FF9900", "#FFA000", "#FFA800", "#FFAF00",
                           "#FFB700", "#FFBF00", "#FFC600", "#FFCE00", "#FFD600", "#FFDD00", "#FFE500", "#FFED00",
                           "#FFF400", "#FFFC00", "#F9FF00", "#F2FF00", "#EAFF00", "#E2FF00", "#DBFF00", "#D3FF00",
                           "#CBFF00", "#C4FF00", "#BCFF00", "#B5FF00", "#ADFF00", "#A5FF00", "#9EFF00", "#96FF00",
                           "#8EFF00", "#87FF00", "#7FFF00", "#77FF00", "#70FF00", "#68FF00", "#60FF00", "#59FF00",
                           "#51FF00", "#49FF00", "#42FF00", "#3AFF00", "#33FF00", "#2BFF00", "#23FF00", "#1CFF00",
                           "#14FF00", "#0CFF00", "#05FF00", "#00FF02", "#00FF0A", "#00FF11", "#00FF19", "#00FF21",
                           "#00FF28", "#00FF30", "#00FF38", "#00FF3F", "#00FF47", "#00FF4F", "#00FF56", "#00FF5E",
                           "#00FF66", "#00FF6D", "#00FF75", "#00FF7C", "#00FF84", "#00FF8C", "#00FF93", "#00FF9B",
                           "#00FFA3", "#00FFAA", "#00FFB2", "#00FFBA", "#00FFC1", "#00FFC9", "#00FFD1", "#00FFD8",
                           "#00FFE0", "#00FFE8", "#00FFEF", "#00FFF7", "#00FFFF", "#00F7FF", "#00EFFF", "#00E8FF",
                           "#00E0FF", "#00D8FF", "#00D1FF", "#00C9FF", "#00C1FF", "#00BAFF", "#00B2FF", "#00AAFF",
                           "#00A3FF", "#009BFF", "#0093FF", "#008CFF", "#0084FF", "#007CFF", "#0075FF", "#006DFF",
                           "#0066FF", "#005EFF", "#0056FF", "#004FFF", "#0047FF", "#003FFF", "#0038FF", "#0030FF",
                           "#0028FF", "#0021FF", "#0019FF", "#0011FF", "#000AFF", "#0002FF", "#0500FF", "#0C00FF",
                           "#1400FF", "#1C00FF", "#2300FF", "#2B00FF", "#3200FF", "#3A00FF", "#4200FF", "#4900FF",
                           "#5100FF", "#5900FF", "#6000FF", "#6800FF", "#7000FF", "#7700FF", "#7F00FF", "#8700FF",
                           "#8E00FF", "#9600FF", "#9E00FF", "#A500FF", "#AD00FF", "#B500FF", "#BC00FF", "#C400FF",
                           "#CC00FF", "#D300FF", "#DB00FF", "#E200FF", "#EA00FF", "#F200FF", "#F900FF", "#FF00FC",
                           "#FF00F4", "#FF00ED", "#FF00E5", "#FF00DD", "#FF00D6", "#FF00CE", "#FF00C6", "#FF00BF",
                           "#FF00B7", "#FF00AF", "#FF00A8", "#FF00A0", "#FF0098", "#FF0091", "#FF0089", "#FF0082",
                           "#FF007A", "#FF0072", "#FF006B", "#FF0063", "#FF005B", "#FF0054", "#FF004C", "#FF0044",
                           "#FF003D", "#FF0035", "#FF002D", "#FF0026", "#FF001E", "#FF0016", "#FF000F", "#FF0007"],
    },
    "light_rainbow": {
        "BG":      "#FFF5F5",
        "PANEL":   "#FFFFFF",
        "BORDER":  "#F4CACA",
        "ACCENT":  "#E40303",
        "ACCENT2": "#FF8C00",
        "TAB":     "#732982",
        "TEXT":    "#2A1111",
        "TEXT2":   "#472020",
        "SUBTEXT": "#757575",
        "GREEN":   "#008026",
        "RED":     "#E40303",
        "YELLOW":  "#FFED00",
        "CYAN":    "#004DFF",
        "ORANGE":  "#FF8C00",
        "STRIPE_COLOURS": ["#FF0000", "#FF0700", "#FF0F00", "#FF1600", "#FF1E00", "#FF2600", "#FF2D00", "#FF3500",
                           "#FF3D00", "#FF4400", "#FF4C00", "#FF5400", "#FF5B00", "#FF6300", "#FF6B00", "#FF7200",
                           "#FF7A00", "#FF8200", "#FF8900", "#FF9100", "#FF9900", "#FFA000", "#FFA800", "#FFAF00",
                           "#FFB700", "#FFBF00", "#FFC600", "#FFCE00", "#FFD600", "#FFDD00", "#FFE500", "#FFED00",
                           "#FFF400", "#FFFC00", "#F9FF00", "#F2FF00", "#EAFF00", "#E2FF00", "#DBFF00", "#D3FF00",
                           "#CBFF00", "#C4FF00", "#BCFF00", "#B5FF00", "#ADFF00", "#A5FF00", "#9EFF00", "#96FF00",
                           "#8EFF00", "#87FF00", "#7FFF00", "#77FF00", "#70FF00", "#68FF00", "#60FF00", "#59FF00",
                           "#51FF00", "#49FF00", "#42FF00", "#3AFF00", "#33FF00", "#2BFF00", "#23FF00", "#1CFF00",
                           "#14FF00", "#0CFF00", "#05FF00", "#00FF02", "#00FF0A", "#00FF11", "#00FF19", "#00FF21",
                           "#00FF28", "#00FF30", "#00FF38", "#00FF3F", "#00FF47", "#00FF4F", "#00FF56", "#00FF5E",
                           "#00FF66", "#00FF6D", "#00FF75", "#00FF7C", "#00FF84", "#00FF8C", "#00FF93", "#00FF9B",
                           "#00FFA3", "#00FFAA", "#00FFB2", "#00FFBA", "#00FFC1", "#00FFC9", "#00FFD1", "#00FFD8",
                           "#00FFE0", "#00FFE8", "#00FFEF", "#00FFF7", "#00FFFF", "#00F7FF", "#00EFFF", "#00E8FF",
                           "#00E0FF", "#00D8FF", "#00D1FF", "#00C9FF", "#00C1FF", "#00BAFF", "#00B2FF", "#00AAFF",
                           "#00A3FF", "#009BFF", "#0093FF", "#008CFF", "#0084FF", "#007CFF", "#0075FF", "#006DFF",
                           "#0066FF", "#005EFF", "#0056FF", "#004FFF", "#0047FF", "#003FFF", "#0038FF", "#0030FF",
                           "#0028FF", "#0021FF", "#0019FF", "#0011FF", "#000AFF", "#0002FF", "#0500FF", "#0C00FF",
                           "#1400FF", "#1C00FF", "#2300FF", "#2B00FF", "#3200FF", "#3A00FF", "#4200FF", "#4900FF",
                           "#5100FF", "#5900FF", "#6000FF", "#6800FF", "#7000FF", "#7700FF", "#7F00FF", "#8700FF",
                           "#8E00FF", "#9600FF", "#9E00FF", "#A500FF", "#AD00FF", "#B500FF", "#BC00FF", "#C400FF",
                           "#CC00FF", "#D300FF", "#DB00FF", "#E200FF", "#EA00FF", "#F200FF", "#F900FF", "#FF00FC",
                           "#FF00F4", "#FF00ED", "#FF00E5", "#FF00DD", "#FF00D6", "#FF00CE", "#FF00C6", "#FF00BF",
                           "#FF00B7", "#FF00AF", "#FF00A8", "#FF00A0", "#FF0098", "#FF0091", "#FF0089", "#FF0082",
                           "#FF007A", "#FF0072", "#FF006B", "#FF0063", "#FF005B", "#FF0054", "#FF004C", "#FF0044",
                           "#FF003D", "#FF0035", "#FF002D", "#FF0026", "#FF001E", "#FF0016", "#FF000F", "#FF0007"],
    },
    "pride_flag": {
        "BG":      "#1A1A1A",
        "PANEL":   "#1c1c1c",
        "BORDER":  "#333333",
        "ACCENT":  "#FFED00",
        "ACCENT2": "#FF8C00",
        "TAB":     "#FFED00",
        "TEXT":    "#FFFFFF",
        "TEXT2":   "#F0F0F0",
        "SUBTEXT": "#CCCCCC",
        "GREEN":   "#008026",
        "RED":     "#E40303",
        "YELLOW":  "#FFED00",
        "CYAN":    "#004DFF",
        "ORANGE":  "#FF8C00",
        "STRIPE_COLOURS": ["#E40303", "#FF8C00", "#FFED00", "#008026", "#004DFF", "#750787"],
    },
    "trans_flag": {
        "BG":      "#0d1f28",
        "PANEL":   "#1a2e36",
        "BORDER":  "#5BCEFA",
        "ACCENT":  "#F5A9B8",
        "ACCENT2": "#5BCEFA",
        "TAB":     "#F5A9B8",
        "TEXT":    "#FFFFFF",
        "TEXT2":   "#e0f4ff",
        "SUBTEXT": "#a8d4e8",
        "GREEN":   "#5BCEFA",
        "RED":     "#F5A9B8",
        "YELLOW":  "#FFFFFF",
        "CYAN":    "#5BCEFA",
        "ORANGE":  "#F5A9B8",
        "STRIPE_COLOURS": ["#5BCEFA", "#F5A9B8", "#FFFFFF", "#F5A9B8", "#5BCEFA"],
    },
    "nonbinary_flag": {
        "BG":      "#1e1230",
        "PANEL":   "#1e1230",
        "BORDER":  "#9C59D1",
        "ACCENT":  "#FFF430",
        "ACCENT2": "#9C59D1",
        "TAB":     "#FFF430",
        "TEXT":    "#FFFFFF",
        "TEXT2":   "#F0F0F0",
        "SUBTEXT": "#DDDDDD",
        "GREEN":   "#9C59D1",
        "RED":     "#FFF430",
        "YELLOW":  "#FFF430",
        "CYAN":    "#FFFFFF",
        "ORANGE":  "#FFF430",
        "STRIPE_COLOURS": ["#FFF430", "#FFFFFF", "#9C59D1", "#2C2C2C"],
    },
    "ace_flag": {
        "BG":      "#161616",
        "PANEL":   "#2a002a",
        "BORDER":  "#800080",
        "ACCENT":  "#B05ACD",
        "ACCENT2": "#CC88EE",
        "TAB":     "#B05ACD",
        "TEXT":    "#FFFFFF",
        "TEXT2":   "#F2F2F2",
        "SUBTEXT": "#CFCFCF",
        "GREEN":   "#B05ACD",
        "RED":     "#f87171",
        "YELLOW":  "#FFFFFF",
        "CYAN":    "#B05ACD",
        "ORANGE":  "#B05ACD",
        "STRIPE_COLOURS": ["#161616", "#808080", "#FFFFFF", "#800080"],
    },
    "bi_flag": {
        "BG":      "#1a0d1a",
        "PANEL":   "#2b1028",
        "BORDER":  "#9B4F96",
        "ACCENT":  "#D60270",
        "ACCENT2": "#9B4F96",
        "TAB":     "#D60270",
        "TEXT":    "#FFFFFF",
        "TEXT2":   "#F5E6F5",
        "SUBTEXT": "#C8A0C8",
        "GREEN":   "#9B4F96",
        "RED":     "#D60270",
        "YELLOW":  "#FFFFFF",
        "CYAN":    "#0038A8",
        "ORANGE":  "#D60270",
        "STRIPE_COLOURS": ["#D60270", "#D60270", "#9B4F96", "#0038A8", "#0038A8"],
    },
    "gay_flag": {
        "BG":      "#00150f",
        "PANEL":   "#002018",
        "BORDER":  "#3D9970",
        "ACCENT":  "#3D9970",
        "ACCENT2": "#70C9A0",
        "TAB":     "#3D9970",
        "TEXT":    "#FFFFFF",
        "TEXT2":   "#E0FFF5",
        "SUBTEXT": "#7ABBA0",
        "GREEN":   "#3D9970",
        "RED":     "#006B54",
        "YELLOW":  "#FFFFFF",
        "CYAN":    "#7BADE2",
        "ORANGE":  "#3D9970",
        "STRIPE_COLOURS": ["#078D70", "#26CEA8", "#98E8C1", "#FFFFFF", "#7BADE2", "#5049CC", "#3D1A8E"],
    },
    "lesbian_flag": {
        "BG":      "#1f0d00",
        "PANEL":   "#2e1500",
        "BORDER":  "#D52D00",
        "ACCENT":  "#FF9A56",
        "ACCENT2": "#FF6D4A",
        "TAB":     "#FF9A56",
        "TEXT":    "#FFFFFF",
        "TEXT2":   "#FFE8DC",
        "SUBTEXT": "#D4907A",
        "GREEN":   "#FF9A56",
        "RED":     "#D52D00",
        "YELLOW":  "#FF9A56",
        "CYAN":    "#A50062",
        "ORANGE":  "#FF9A56",
        "STRIPE_COLOURS": ["#D52D00", "#FF9A56", "#FFFFFF", "#D362A4", "#A50062"],
    },
    "pan_flag": {
        "BG":      "#0f0f1a",
        "PANEL":   "#1a1a2e",
        "BORDER":  "#FFD800",
        "ACCENT":  "#FF218C",
        "ACCENT2": "#FFD800",
        "TAB":     "#FF218C",
        "TEXT":    "#FFFFFF",
        "TEXT2":   "#F5F5FF",
        "SUBTEXT": "#BBBBDD",
        "GREEN":   "#21B1FF",
        "RED":     "#FF218C",
        "YELLOW":  "#FFD800",
        "CYAN":    "#21B1FF",
        "ORANGE":  "#FF218C",
        "STRIPE_COLOURS": ["#FF218C", "#FF218C", "#FFD800", "#FFD800", "#21B1FF", "#21B1FF"],
    },
    "genderqueer_flag": {
        "BG":      "#141020",
        "PANEL":   "#1e1630",
        "BORDER":  "#B57EDC",
        "ACCENT":  "#B57EDC",
        "ACCENT2": "#CCAAEE",
        "TAB":     "#B57EDC",
        "TEXT":    "#FFFFFF",
        "TEXT2":   "#F0EAFF",
        "SUBTEXT": "#BBA8D8",
        "GREEN":   "#498019",
        "RED":     "#B57EDC",
        "YELLOW":  "#FFFFFF",
        "CYAN":    "#498019",
        "ORANGE":  "#B57EDC",
        "STRIPE_COLOURS": ["#B57EDC", "#B57EDC", "#FFFFFF", "#FFFFFF", "#498019", "#498019"],
    },
    "aro_flag": {
        "BG":      "#0a120a",
        "PANEL":   "#101e10",
        "BORDER":  "#3DA542",
        "ACCENT":  "#3DA542",
        "ACCENT2": "#A8D379",
        "TAB":     "#3DA542",
        "TEXT":    "#FFFFFF",
        "TEXT2":   "#E8F5E8",
        "SUBTEXT": "#8CB88C",
        "GREEN":   "#3DA542",
        "RED":     "#A8D379",
        "YELLOW":  "#FFFFFF",
        "CYAN":    "#3DA542",
        "ORANGE":  "#A8D379",
        "STRIPE_COLOURS": ["#3DA542", "#A8D379", "#FFFFFF", "#A9A9A9", "#000000"],
    },
    "genderfluid_flag": {
        "BG":      "#0d0014",
        "PANEL":   "#170020",
        "BORDER":  "#BE18D6",
        "ACCENT":  "#FF76A4",
        "ACCENT2": "#BE18D6",
        "TAB":     "#FF76A4",
        "TEXT":    "#FFFFFF",
        "TEXT2":   "#F8E8FF",
        "SUBTEXT": "#C099CC",
        "GREEN":   "#BE18D6",
        "RED":     "#FF76A4",
        "YELLOW":  "#FFFFFF",
        "CYAN":    "#3300BE",
        "ORANGE":  "#FF76A4",
        "STRIPE_COLOURS": ["#FF76A4", "#FFFFFF", "#BE18D6", "#000000", "#3300BE"],
    },
    "intersex_flag": {
        "BG":      "#1a1400",
        "PANEL":   "#2b2200",
        "BORDER":  "#FFD800",
        "ACCENT":  "#FFD800",
        "ACCENT2": "#FFE84D",
        "TAB":     "#FFD800",
        "TEXT":    "#FFFFFF",
        "TEXT2":   "#FFF8CC",
        "SUBTEXT": "#CCAA00",
        "GREEN":   "#FFD800",
        "RED":     "#7A00C8",
        "YELLOW":  "#FFD800",
        "CYAN":    "#7A00C8",
        "ORANGE":  "#FFD800",
        "STRIPE_COLOURS": ["#FFD800", "#FFD800", "#FFD800", "#7A00C8", "#7A00C8", "#FFD800", "#FFD800", "#FFD800"],
    },
    "demi_flag": {
        "BG":      "#121212",
        "PANEL":   "#1e1e1e",
        "BORDER":  "#7A7A7A",
        "ACCENT":  "#9966CC",
        "ACCENT2": "#BB99EE",
        "TAB":     "#9966CC",
        "TEXT":    "#FFFFFF",
        "TEXT2":   "#F0F0F0",
        "SUBTEXT": "#AAAAAA",
        "GREEN":   "#9966CC",
        "RED":     "#7A7A7A",
        "YELLOW":  "#FFFFFF",
        "CYAN":    "#9966CC",
        "ORANGE":  "#9966CC",
        "STRIPE_COLOURS": ["#000000", "#7A7A7A", "#FFFFFF", "#9966CC", "#FFFFFF", "#7A7A7A"],
    },
    "omni_flag": {
        "BG":      "#16000B",
        "PANEL":   "#260014",
        "BORDER":  "#FF8C69",
        "ACCENT":  "#FF69B4",
        "ACCENT2": "#8B00FF",
        "TAB":     "#FF69B4",
        "TEXT":    "#FFFFFF",
        "TEXT2":   "#FFF0F7",
        "SUBTEXT": "#D5A0B8",
        "GREEN":   "#57C785",
        "RED":     "#FF69B4",
        "YELLOW":  "#FFD166",
        "CYAN":    "#7B68EE",
        "ORANGE":  "#FF8C69",
        "STRIPE_COLOURS": ["#FF69B4", "#FF8C69", "#FF69B4", "#FFFFFF", "#8B00FF"],
    },
}

THEME_LABELS = {
    "dark":             "Dark",
    "rich_purple":      "Rich Purple",
    "dark_sand":        "Dark Sand",
    "absolute_zero":    "Absolute Zero",
    "light_purple":     "Light Purple",
    "light_sand":       "Light Sand",
    "mint":             "Mint",
    "dark_mint":        "Dark Mint",
    "dark_red":         "Dark Red",
    "light_red":        "Light Red",
    "light_blue":       "Light Blue",
    "dark_rainbow":     "Dark Rainbow",
    "light_rainbow":    "Light Rainbow",
    "pride_flag":       "Pride Flag",
    "trans_flag":       "Trans Flag",
    "nonbinary_flag":   "Nonbinary Flag",
    "ace_flag":         "Ace Flag",
    "bi_flag":          "Bi Flag",
    "gay_flag":         "Gay Flag",
    "lesbian_flag":     "Lesbian Flag",
    "pan_flag":         "Pan Flag",
    "genderqueer_flag": "Genderqueer Flag",
    "aro_flag":         "Aro Flag",
    "genderfluid_flag": "Genderfluid Flag",
    "intersex_flag":    "Intersex Flag",
    "demi_flag":        "Demi Flag",
    "omni_flag":        "Omni Flag",
}




def set_theme(mode: str):
    global colour_mode
    palette = THEMES.get(mode, THEMES["rich_purple"])
    colour_mode = mode if mode in THEMES else "new"
    g = globals()
    for key, value in palette.items():
        g[key] = value
    if "STRIPE_COLOURS" not in palette:
        g["STRIPE_COLOURS"] = None



set_theme(colour_mode)

# ── Qt helpers ────────────────────────────────────────────────────────────
# Everything below this line is the Qt-side addition. The colour constants
# above (BG, PANEL, ACCENT, etc.) are set as module globals by set_theme()
# and read directly here — same pattern the rest of the app already uses.

STRIPE_WIDTH = 28  # px, same tiling width as the old Tk draw_stripes()


def qt_font(size: int, bold: bool = False) -> QFont:
    families = QFontDatabase.families()
    family = FONT if FONT in families else "Consolas"
    f = QFont(family, size)
    if bold:
        f.setBold(True)
    return f


def accent_button_qss() -> str:
    """Inline stylesheet for the 'accent' button look (bright ACCENT fill,
    BG text) — e.g. primary actions like Close/Next.

    NOTE: this used to be applied via `button.setObjectName("accentButton")`
    plus a `QPushButton#accentButton { ... }` rule in qss(). That breaks
    silently (renders with no visible background at all) whenever the
    button sits inside ANY ancestor widget that also has its own
    setStyleSheet() call — which is nearly everywhere in this app, since
    every panel/frame sets its own background colour that way. Confirmed
    via isolated testing: the objectName-selector rule gets shadowed by
    the ancestor's stylesheet, even though the ancestor's rule doesn't
    mention QPushButton at all. Setting the style directly on the button
    itself (this function) sidesteps the issue entirely."""
    return (
        f"QPushButton {{ background-color: {ACCENT}; color: {BG}; "
        f"border: none; border-radius: 3px; padding: 6px 14px; font-weight: bold; }}"
        f"QPushButton:hover {{ background-color: {ACCENT2}; }}"
    )


def subtle_button_qss() -> str:
    """Inline stylesheet for the 'subtle' button look (PANEL fill, SUBTEXT
    text) — e.g. secondary actions like Help/Settings/Back. See the note
    on accent_button_qss() above for why this is applied inline rather
    than via objectName + global QSS."""
    return (
        f"QPushButton {{ background-color: {PANEL}; color: {SUBTEXT}; "
        f"border: none; border-radius: 3px; padding: 6px 14px; }}"
        f"QPushButton:hover {{ background-color: {BORDER}; color: {TEXT}; }}"
    )


def section_caption_qss(bg: str = None) -> str:
    """Small background 'chip' behind section-header captions (e.g.
    'Live Chatbox Preview', 'Configuration', 'Features'). Without this
    they're just floating text directly on whatever's behind them, which
    gets hard to read against busy flag-stripe themes or blends into a
    same-coloured parent panel.

    Defaults to PANEL (for captions sitting directly on the stripe/BG
    layer, e.g. in the chatbox tab). Pass bg=BORDER for captions that
    already sit on a PANEL-coloured parent (settings dialog, dev menu),
    so the chip doesn't disappear into its own background."""
    bg = bg or PANEL
    return (
        f"color: {ACCENT2}; background-color: {bg}; "
        f"padding: 3px 10px; border-radius: 3px; border: none;"
    )


def line_edit_qss() -> str:
    """Inline stylesheet for QLineEdit inputs. Same root cause as
    accent_button_qss()/subtle_button_qss() above: the global QSS rule
    for QLineEdit gets silently shadowed whenever the input sits inside
    any ancestor widget that has its own setStyleSheet() call (which is
    true for basically every module capsule / row / card in this app),
    leaving text inputs with no visible background at all."""
    return (
        f"QLineEdit {{ background-color: {PANEL}; color: {TEXT}; "
        f"border: 1px solid {BORDER}; border-radius: 2px; padding: 3px 6px; "
        f"selection-background-color: {ACCENT}; }}"
        f"QLineEdit:focus {{ border: 1px solid {ACCENT}; }}"
    )


def qss() -> str:
    """Global stylesheet approximating the old Tk look: flat buttons, PANEL
    surfaces, ACCENT highlights, BORDER outlines. Call again (and re-apply
    via app.setStyleSheet(theme.qss())) any time set_theme() changes the
    active palette."""
    return f"""
    QWidget {{
        background-color: {BG};
        color: {TEXT};
        font-family: "{FONT}";
        border: none;
    }}

    QMainWindow, QDialog {{
        background-color: {BG};
    }}

    /* ── Tab bar (mirrors ttk Notebook: PANEL tabs, BG when selected) ── */
    QTabWidget::pane {{
        border: none;
        background: {BG};
    }}
    QTabBar::tab {{
        background: {PANEL};
        color: {SUBTEXT};
        padding: 6px 16px;
        border: none;
        font-weight: bold;
    }}
    QTabBar::tab:selected {{
        background: {BG};
        color: {TAB};
    }}

    /* ── Flat buttons (Tk relief="flat") ── */
    QPushButton {{
        background-color: {PANEL};
        color: {ACCENT};
        border: none;
        border-radius: 3px;
        padding: 6px 14px;
        font-weight: bold;
    }}
    QPushButton:hover {{
        background-color: {BORDER};
        color: {TEXT};
    }}
    QPushButton:disabled {{
        color: {SUBTEXT};
    }}
    /* NOTE: accent/subtle button variants are applied inline via
       accent_button_qss() / subtle_button_qss() above, not via objectName
       selectors here — see the docstring on those functions for why. */

    /* ── Line edits (Tk Entry) ── */
    QLineEdit {{
        background-color: {PANEL};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 2px;
        padding: 3px 6px;
        selection-background-color: {ACCENT};
    }}
    QLineEdit:focus {{
        border: 1px solid {ACCENT};
    }}

    /* ── Text preview box (Tk Text) ── */
    QPlainTextEdit, QTextEdit {{
        background-color: {PANEL};
        color: {TEXT};
        border: none;
        selection-background-color: {ACCENT};
    }}

    /* ── Scrollbars (thin, flat) ── */
    QScrollBar:vertical {{
        background: {BG};
        width: 12px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER};
        min-height: 24px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {ACCENT2};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}

    /* ── Slider (opacity) ── */
    QSlider::groove:horizontal {{
        background: {BG};
        height: 6px;
        border-radius: 3px;
    }}
    QSlider::handle:horizontal {{
        background: {ACCENT};
        width: 14px;
        margin: -5px 0;
        border-radius: 7px;
    }}
    QSlider::handle:horizontal:hover {{
        background: {ACCENT2};
    }}

    /* ── Checkbox / Radio ── */
    QCheckBox, QRadioButton {{
        color: {TEXT};
        spacing: 8px;
    }}
    QCheckBox::indicator, QRadioButton::indicator {{
        width: 14px;
        height: 14px;
        border: 1px solid {BORDER};
        background: {PANEL};
    }}
    QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
        background: {ACCENT};
        border: 1px solid {ACCENT};
    }}

    QMenu {{
        background-color: {PANEL};
        color: {TEXT};
        border: 1px solid {BORDER};
    }}
    QMenu::item:selected {{
        background-color: {ACCENT};
        color: {BG};
    }}

    QToolTip {{
        background-color: {PANEL};
        color: {TEXT};
        border: 1px solid {BORDER};
    }}
    """


class TextChip(QLabel):
    """A QLabel with a translucent background 'chip' painted behind its
    text — used for section captions (Configuration, Live Chatbox
    Preview) and field labels (OSC IP, etc). A plain stylesheet
    background-color is always fully opaque and can't respond to the
    transparency slider; this paints its own background via QPainter
    (same technique as StripeBackground) so set_bg_alpha() can fade it
    along with the rest of the window's background."""

    def __init__(self, text="", *, fg=None, bg=None, radius=3,
                 padding="3px 10px", parent=None):
        super().__init__(text, parent)
        self._chip_bg = QColor(bg or PANEL)
        self._bg_alpha = 1.0
        self._radius = radius
        self.setStyleSheet(
            f"color: {fg or ACCENT2}; background: transparent; "
            f"padding: {padding}; border: none;"
        )

    def set_bg_alpha(self, alpha: float):
        self._bg_alpha = max(0.0, min(1.0, alpha))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        c = QColor(self._chip_bg)
        c.setAlpha(round(self._bg_alpha * 255))
        painter.setCompositionMode(QPainter.CompositionMode_Source)
        painter.setBrush(c)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), self._radius, self._radius)
        painter.end()
        super().paintEvent(event)


class StripeBackground(QWidget):
    """Paints repeating ~45° diagonal stripes across the whole widget when a
    flag theme is active (STRIPE_COLOURS set); otherwise just fills BG.
    Direct replacement for the old draw_stripes()-on-a-Tk-canvas approach —
    child widgets are added on top via a normal layout, and the stripes show
    through any gap that isn't covered by an opaque PANEL-coloured widget.

    Also supports an adjustable fill alpha (set_bg_alpha) for background-only
    window transparency — see ui/app.py. Only this fill uses alpha < 255;
    every other widget in the app stays fully opaque."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(False)
        self._bg_alpha = 1.0  # 0.0-1.0, applied to the background fill only

    def set_bg_alpha(self, alpha: float):
        self._bg_alpha = max(0.0, min(1.0, alpha))
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        w, h = self.width(), self.height()
        a = round(self._bg_alpha * 255)

        colours = STRIPE_COLOURS
        if not colours:
            c = QColor(BG)
            c.setAlpha(a)
            painter.setCompositionMode(QPainter.CompositionMode_Source)
            painter.fillRect(self.rect(), c)
            return

        bg = QColor(BG)
        bg.setAlpha(a)
        painter.setCompositionMode(QPainter.CompositionMode_Source)
        painter.fillRect(self.rect(), bg)
        # Keep Source mode (not SourceOver) for the stripes too — SourceOver
        # would blend each stripe on top of the already-transparent base,
        # and stacking two alpha layers like that compounds toward more
        # opaque than the slider says (e.g. two 50%-alpha layers combine to
        # ~75%, not 50%). Source just replaces the pixel outright, keeping
        # a single consistent alpha across the whole background.

        stripe_w = STRIPE_WIDTH
        cycle = stripe_w * len(colours)
        extent = w + h + cycle * 2

        start = -cycle
        while start < extent:
            for i, colour in enumerate(colours):
                x0 = start + i * stripe_w
                poly = QPolygonF([
                    QPointF(x0, 0),
                    QPointF(x0 + stripe_w, 0),
                    QPointF(x0 + stripe_w + h, h),
                    QPointF(x0 + h, h),
                ])
                sc = QColor(colour)
                sc.setAlpha(a)
                painter.setBrush(sc)
                painter.setPen(Qt.NoPen)
                painter.drawPolygon(poly)
            start += cycle
