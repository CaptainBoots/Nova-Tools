"""
gpu_ids.py
──────────
PCI vendor:device ID → human readable GPU name.

Imported by hardware/gpu.py only. Edit this file to add new GPUs
without touching any other module.

Format:  "vendor_id:device_id" : "Display Name"
All IDs lowercase.
"""

AMBIGUOUS_IDS: set[str] = {
    "1002:7550",  # Radeon RX 9070 / 9070 XT
}

GPU_ID_MAP: dict[str, str] = {

    # ══════════════════════════════════════════════════════════════
    # AMD — RX 9000 series (RDNA 4)
    # ══════════════════════════════════════════════════════════════
    "1002:7550": "Radeon RX 9070 / 9070 XT",
    "1002:7551": "Radeon AI PRO R9700",
    "1002:7590": "Radeon RX 9060 XT",
    "1002:7518": "Radeon RX 9070 XT",
    "1002:7580": "Radeon RX 9070",
    "1002:7591": "Radeon RX 9060",

    # ══════════════════════════════════════════════════════════════
    # AMD — RX 7000 series (RDNA 3)
    # ══════════════════════════════════════════════════════════════
    "1002:744c": "Radeon RX 7900 XTX",
    "1002:747e": "Radeon RX 7800 XT",
    "1002:7480": "Radeon RX 7600 XT",
    "1002:7483": "Radeon RX 7600M XT",
    "1002:7499": "Radeon RX 7400",
    "1002:73ef": "Radeon RX 6650 XT",
    "1002:73ff": "Radeon RX 6600 XT",

    # ══════════════════════════════════════════════════════════════
    # AMD — RX 6000 series (RDNA 2)
    # ══════════════════════════════════════════════════════════════
    "1002:73bf": "Radeon RX 6900 XT",
    "1002:73af": "Radeon RX 6800 XT",
    "1002:73a5": "Radeon RX 6950 XT",
    "1002:73df": "Radeon RX 6700 XT",
    "1002:73a3": "Radeon PRO W6800",
    "1002:73a4": "Radeon RX 6500 XT",
    "1002:743f": "Radeon RX 6400",

    # ══════════════════════════════════════════════════════════════
    # AMD — RX 5000 series (RDNA 1)
    # ══════════════════════════════════════════════════════════════
    "1002:731f": "Radeon RX 5700 XT",
    "1002:7340": "Radeon RX 5500 XT",
    "1002:7360": "Radeon RX 5600 XT",

    # ══════════════════════════════════════════════════════════════
    # AMD — Vega / Polaris
    # ══════════════════════════════════════════════════════════════
    "1002:687f": "Radeon RX Vega 64",
    "1002:6fdf": "Radeon RX 580",
    "1002:67df": "Radeon RX 480",
    "1002:6995": "Radeon RX 470",
    "1002:699f": "Radeon RX 460",
    "1002:67ff": "Radeon RX 560",

    # ══════════════════════════════════════════════════════════════
    # AMD — iGPU / APU
    # ══════════════════════════════════════════════════════════════
    "1002:150e": "Radeon 890M (Strix Point)",
    "1002:15bf": "Radeon 780M (Phoenix)",
    "1002:1900": "Radeon 760M (Hawk Point)",
    "1002:1681": "Radeon 680M (Rembrandt)",
    "1002:164e": "Radeon Graphics (Raphael)",
    "1002:13c0": "Radeon Graphics (Granite Ridge)",
    "1002:163f": "Radeon (Van Gogh — Steam Deck)",
    "1002:1638": "Radeon Vega (Cezanne)",
    "1002:1636": "Radeon Vega (Renoir)",
    "1002:15dd": "Radeon Vega (Raven Ridge)",

    # ══════════════════════════════════════════════════════════════
    # NVIDIA — RTX 50 series (Blackwell)
    # ══════════════════════════════════════════════════════════════
    "10de:2b85": "GeForce RTX 5090",
    "10de:2b87": "GeForce RTX 5080",
    "10de:2b89": "GeForce RTX 5070 Ti",
    "10de:2b8a": "GeForce RTX 5070",
    "10de:2b8c": "GeForce RTX 5060 Ti",
    "10de:2d04": "GeForce RTX 5060 Ti",
    "10de:2b91": "GeForce RTX 5060",

    # ══════════════════════════════════════════════════════════════
    # NVIDIA — RTX 40 series (Ada Lovelace)
    # ══════════════════════════════════════════════════════════════
    "10de:2684": "GeForce RTX 4090",
    "10de:2702": "GeForce RTX 4080 Super",
    "10de:2704": "GeForce RTX 4080",
    "10de:2705": "GeForce RTX 4070 Ti Super",
    "10de:2782": "GeForce RTX 4070 Ti",
    "10de:2860": "GeForce RTX 4070 Super",
    "10de:2786": "GeForce RTX 4070",
    "10de:28a0": "GeForce RTX 4060 Ti",
    "10de:2803": "GeForce RTX 4060 Ti",
    "10de:2882": "GeForce RTX 4060",

    # ══════════════════════════════════════════════════════════════
    # NVIDIA — RTX 30 series (Ampere)
    # ══════════════════════════════════════════════════════════════
    "10de:2204": "GeForce RTX 3090 Ti",
    "10de:2203": "GeForce RTX 3090",
    "10de:2208": "GeForce RTX 3080 Ti",
    "10de:2206": "GeForce RTX 3080",
    "10de:2484": "GeForce RTX 3070 Ti",
    "10de:2488": "GeForce RTX 3070",
    "10de:2503": "GeForce RTX 3060 Ti",
    "10de:2504": "GeForce RTX 3060",
    "10de:2571": "GeForce RTX 3050",

    # ══════════════════════════════════════════════════════════════
    # NVIDIA — RTX 20 series (Turing)
    # ══════════════════════════════════════════════════════════════
    "10de:1e04": "GeForce RTX 2080 Ti",
    "10de:1e82": "GeForce RTX 2080 Super",
    "10de:1e87": "GeForce RTX 2080",
    "10de:1e84": "GeForce RTX 2070 Super",
    "10de:1f02": "GeForce RTX 2070",
    "10de:1f06": "GeForce RTX 2060 Super",
    "10de:1f08": "GeForce RTX 2060",

    # ══════════════════════════════════════════════════════════════
    # NVIDIA — GTX 16 / 10 series
    # ══════════════════════════════════════════════════════════════
    "10de:2182": "GeForce GTX 1660 Ti",
    "10de:21c4": "GeForce GTX 1660 Super",
    "10de:2184": "GeForce GTX 1660",
    "10de:2187": "GeForce GTX 1650 Super",
    "10de:1f82": "GeForce GTX 1650",
    "10de:1b80": "GeForce GTX 1080 Ti",
    "10de:1b81": "GeForce GTX 1080",
    "10de:1b82": "GeForce GTX 1070 Ti",
    "10de:1b83": "GeForce GTX 1070",
    "10de:1c02": "GeForce GTX 1060 6GB",
    "10de:1c03": "GeForce GTX 1060 3GB",
    "10de:1c81": "GeForce GTX 1050 Ti",
    "10de:1c82": "GeForce GTX 1050",

    # ══════════════════════════════════════════════════════════════
    # Intel — Arc (Alchemist / Battlemage)
    # ══════════════════════════════════════════════════════════════
    "8086:56a0": "Intel Arc A770",
    "8086:56a1": "Intel Arc A750",
    "8086:56a5": "Intel Arc A380",
    "8086:e20b": "Intel Arc B770",
    "8086:e20c": "Intel Arc B580",

    # ══════════════════════════════════════════════════════════════
    # Intel — UHD / Iris Xe
    # ══════════════════════════════════════════════════════════════
    "8086:9a49": "Intel Iris Xe (Tiger Lake)",
    "8086:46d0": "Intel UHD 770 (Alder Lake)",
    "8086:a780": "Intel UHD 770 (Raptor Lake)",
    "8086:3e92": "Intel UHD 630 (Coffee Lake)",
    "8086:9bc5": "Intel UHD 630 (Comet Lake)",
    "8086:5912": "Intel HD 630 (Kaby Lake)",
}