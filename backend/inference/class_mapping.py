"""Class name mapping: SOP semantic names → YOLO COCO detectable classes.

SOP rules use domain-specific names like "board", "solder", "tool" which
don't exist in COCO. This module provides a configurable mapping layer so
the rule engine can match against what YOLO actually detects.
"""

# Default mapping: SOP semantic name → list of COCO classes that could represent it
# Users can extend this via YAML config or API
DEFAULT_MAPPING: dict[str, list[str]] = {
    # Manufacturing / assembly
    "board":        ["book", "cell phone", "laptop", "tv", "dining table"],
    "solder":       ["bottle", "cup", "wine glass"],
    "tool":         ["scissors", "knife", "bottle", "fork", "spoon"],
    "part":         ["bottle", "cup", "cell phone", "book"],
    "screwdriver":  ["knife", "scissors", "toothbrush"],
    "wrench":       ["scissors", "remote", "toothbrush"],
    "label":        ["book", "cell phone"],
    "box":          ["suitcase", "backpack", "handbag"],
    "tray":         ["bowl", "sink", "dining table"],
    "pcb":          ["book", "cell phone", "laptop"],
    "component":    ["bottle", "cup", "cell phone"],
    "cable":        ["tie", "toothbrush"],
    "connector":    ["cell phone", "remote"],
    "screws":       ["scissors", "toothbrush"],
    "magnifier":    ["bottle", "wine glass"],
    "tape":         ["scissors", "toothbrush"],

    # Quality inspection
    "defect":       ["scissors", "knife"],
    "product":      ["bottle", "cup", "cell phone", "book"],
    "package":      ["suitcase", "box", "backpack"],

    # General
    "hand":         ["person"],
    "glove":        ["person"],
    "apron":        ["person"],
    "person":       ["person"],
    "chair":        ["chair"],
    "table":        ["dining table"],
    "monitor":      ["tv", "laptop", "cell phone"],
}


def build_reverse_mapping(mapping: dict[str, list[str]] | None = None) -> dict[str, set[str]]:
    """Build reverse mapping: COCO class → set of SOP semantic names.

    This allows the rule engine to quickly find which SOP names a detected
    COCO class corresponds to.
    """
    source = mapping or DEFAULT_MAPPING
    reverse: dict[str, set[str]] = {}
    for sop_name, coco_classes in source.items():
        for coco_cls in coco_classes:
            if coco_cls not in reverse:
                reverse[coco_cls] = set()
            reverse[coco_cls].add(sop_name)
    return reverse


def resolve_expected_objects(
    expected_objects: list[str],
    mapping: dict[str, list[str]] | None = None,
) -> set[str]:
    """Resolve SOP expected_objects to the full set of COCO class names to match.

    If an expected object is already a COCO class name, it's kept as-is.
    If it has a mapping, all mapped COCO classes are included.

    Args:
        expected_objects: List of SOP semantic class names
        mapping: Custom mapping dict (uses DEFAULT_MAPPING if None)

    Returns:
        Set of COCO class names to match against
    """
    source = mapping or DEFAULT_MAPPING
    resolved: set[str] = set()

    # Build a set of all known COCO class names for direct match detection
    all_coco_classes: set[str] = set()
    for coco_list in source.values():
        all_coco_classes.update(coco_list)
    # Also include the 80 standard COCO classes
    coco_80 = {
        "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train",
        "truck", "boat", "traffic light", "fire hydrant", "stop sign",
        "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep",
        "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella",
        "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard",
        "sports ball", "kite", "baseball bat", "baseball glove", "skateboard",
        "surfboard", "tennis racket", "bottle", "wine glass", "cup", "fork",
        "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
        "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair",
        "couch", "potted plant", "bed", "dining table", "toilet", "tv",
        "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave",
        "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase",
        "scissors", "teddy bear", "hair drier", "toothbrush",
    }
    all_coco_classes.update(coco_80)

    for obj in expected_objects:
        # Always keep the original name (for custom-trained models)
        resolved.add(obj)
        if obj in source:
            # Also add mapped COCO classes
            resolved.update(source[obj])

    return resolved


def get_mapping_info(mapping: dict[str, list[str]] | None = None) -> dict:
    """Return mapping info for API/debugging."""
    source = mapping or DEFAULT_MAPPING
    return {
        "total_mappings": len(source),
        "mappings": {k: v for k, v in source.items()},
    }
