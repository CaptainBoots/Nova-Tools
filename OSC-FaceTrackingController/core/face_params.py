"""
core/face_params.py
────────────────────
Facial morph target parameter definitions: category -> list of
(name, lo, hi, default) tuples, used to build the slider UI.
"""

FACE_PARAMS = {
    "\U0001F441  Eyes": [
        ("EyeLidRight", 0.0, 1.0, 1.0),
        ("EyeLidLeft", 0.0, 1.0, 1.0),
        ("EyeRightX", -1.0, 1.0, 0.0),
        ("EyeRightY", -1.0, 1.0, 0.0),
        ("EyeLeftX", -1.0, 1.0, 0.0),
        ("EyeLeftY", -1.0, 1.0, 0.0),
        ("EyeSquintRight", 0.0, 1.0, 0.0),
        ("EyeSquintLeft", 0.0, 1.0, 0.0),
        ("EyeWideRight", 0.0, 1.0, 0.0),
        ("EyeWideLeft", 0.0, 1.0, 0.0),
    ],
    "\U0001F928 Brows": [
        ("BrowInnerUp", 0.0, 1.0, 0.0),
        ("BrowOuterUpRight", 0.0, 1.0, 0.0),
        ("BrowOuterUpLeft", 0.0, 1.0, 0.0),
        ("BrowDownRight", 0.0, 1.0, 0.0),
        ("BrowDownLeft", 0.0, 1.0, 0.0),
        ("BrowExpressionRight", -1.0, 1.0, 0.0),
        ("BrowExpressionLeft", -1.0, 1.0, 0.0),
    ],
    "\U0001F444 Mouth": [
        ("JawOpen", 0.0, 1.0, 0.0),
        ("JawX", -1.0, 1.0, 0.0),
        ("JawForward", 0.0, 1.0, 0.0),
        ("MouthSmileRight", 0.0, 1.0, 0.0),
        ("MouthSmileLeft", 0.0, 1.0, 0.0),
        ("MouthSadRight", 0.0, 1.0, 0.0),
        ("MouthSadLeft", 0.0, 1.0, 0.0),
        ("MouthPout", 0.0, 1.0, 0.0),
        ("MouthRaiserUpper", 0.0, 1.0, 0.0),
        ("MouthRaiserLower", 0.0, 1.0, 0.0),
        ("LipSuckUpper", 0.0, 1.0, 0.0),
        ("LipSuckLower", 0.0, 1.0, 0.0),
        ("LipFunnelUpper", 0.0, 1.0, 0.0),
        ("LipFunnelLower", 0.0, 1.0, 0.0),
    ],
    "\U0001F443 Cheek / Nose": [
        ("CheekPuffRight", 0.0, 1.0, 0.0),
        ("CheekPuffLeft", 0.0, 1.0, 0.0),
        ("CheekSuckRight", 0.0, 1.0, 0.0),
        ("CheekSuckLeft", 0.0, 1.0, 0.0),
        ("NoseSneerRight", 0.0, 1.0, 0.0),
        ("NoseSneerLeft", 0.0, 1.0, 0.0),
    ],
    "\U0001F445 Tongue": [
        ("TongueOut", 0.0, 1.0, 0.0),
        ("TongueX", -1.0, 1.0, 0.0),
        ("TongueY", -1.0, 1.0, 0.0),
        ("TongueRoll", 0.0, 1.0, 0.0),
        ("TongueBendDown", 0.0, 1.0, 0.0),
        ("TongueCurlUp", 0.0, 1.0, 0.0),
        ("TongueSquish", 0.0, 1.0, 0.0),
        ("TongueFlat", 0.0, 1.0, 0.0),
    ],
}
