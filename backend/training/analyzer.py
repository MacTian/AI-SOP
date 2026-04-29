"""Training analyzer: identifies steps from recorded frames."""

import logging
from collections import Counter

from backend.training.session import FrameRecord

logger = logging.getLogger(__name__)


class DetectedStep:
    """A step identified by the analyzer."""
    step_id: str
    name: str
    order: int
    start_time: float
    end_time: float
    duration: float
    expected_objects: list[str]
    min_confidence: float
    frame_count: int
    dominant_objects: list[str]  # most frequent objects in this step


class StepAnalyzer:
    """Analyzes recorded frames to identify SOP steps.

    Algorithm:
    1. Compute object set for each frame
    2. Detect change points (when object set changes significantly)
    3. Group consecutive similar frames into steps
    4. Generate step metadata from detection results
    """

    def __init__(
        self,
        change_threshold: float = 0.3,  # min Jaccard distance to trigger step change
        min_step_frames: int = 5,  # minimum frames per step
        min_step_duration: float = 2.0,  # minimum seconds per step
    ):
        self.change_threshold = change_threshold
        self.min_step_frames = min_step_frames
        self.min_step_duration = min_step_duration

    def analyze(self, frames: list[FrameRecord]) -> list[dict]:
        """Analyze frames and return identified steps.

        Returns list of step dicts ready to be used in SOP definition.
        """
        if len(frames) < self.min_step_frames:
            logger.warning(f"Too few frames ({len(frames)}) for analysis")
            return []

        # Step 1: Compute object sets per frame
        frame_sets = []
        for f in frames:
            objects = {d["class_name"] for d in f.detections}
            frame_sets.append(objects)

        # Step 2: Detect change points
        change_points = [0]  # always start with first frame
        for i in range(1, len(frame_sets)):
            prev = frame_sets[i - 1]
            curr = frame_sets[i]
            if not prev and not curr:
                continue
            # Jaccard distance
            intersection = len(prev & curr)
            union = len(prev | curr)
            if union > 0:
                similarity = intersection / union
                if similarity < (1 - self.change_threshold):
                    change_points.append(i)

        change_points.append(len(frames))

        # Step 3: Group frames into segments
        segments = []
        for i in range(len(change_points) - 1):
            start = change_points[i]
            end = change_points[i + 1]
            if end - start >= self.min_step_frames:
                segments.append((start, end))
            else:
                # Merge with previous segment if too small
                if segments:
                    prev_start, _ = segments[-1]
                    segments[-1] = (prev_start, end)
                else:
                    segments.append((start, end))

        # Step 4: Generate step metadata
        steps = []
        for i, (start, end) in enumerate(segments):
            seg_frames = frames[start:end]
            step = self._analyze_segment(i, seg_frames, frames[0].timestamp)
            steps.append(step)

        # Step 5: Merge consecutive steps with same dominant objects
        merged = self._merge_similar_steps(steps)

        logger.info(f"Analysis complete: {len(merged)} steps identified from {len(frames)} frames")
        return merged

    def _analyze_segment(self, index: int, frames: list[FrameRecord], base_time: float) -> dict:
        """Analyze a segment of frames to produce a step definition."""
        # Count all detected objects
        object_counter: Counter = Counter()
        confidence_sums: dict[str, float] = {}
        total_conf: float = 0.0
        conf_count: int = 0

        for f in frames:
            for d in f.detections:
                name = d["class_name"]
                object_counter[name] += 1
                confidence_sums[name] = confidence_sums.get(name, 0) + d["confidence"]
                total_conf += d["confidence"]
                conf_count += 1

        # Top objects (appearing in > 30% of frames)
        threshold = len(frames) * 0.3
        dominant = [name for name, count in object_counter.items() if count >= threshold]
        if not dominant:
            dominant = [name for name, _ in object_counter.most_common(3)]

        # Average confidence for dominant objects
        avg_conf = 0.5
        if dominant:
            confs = []
            for name in dominant:
                count = object_counter[name]
                if count > 0:
                    confs.append(confidence_sums[name] / count)
            if confs:
                avg_conf = sum(confs) / len(confs)

        # Step name based on dominant objects
        step_name = self._generate_step_name(dominant, index)

        # Duration
        start_time = frames[0].timestamp
        end_time = frames[-1].timestamp
        duration = end_time - start_time

        return {
            "step_id": f"auto_step_{index + 1}",
            "name": step_name,
            "description": f"自动识别的步骤 {index + 1}",
            "order": index,
            "estimated_duration": max(int(duration), 5),
            "timeout": max(int(duration * 3), 30),
            "expected_objects": dominant,
            "min_confidence": round(max(avg_conf - 0.1, 0.3), 2),
            "required_count": 1,
            "_start_time": start_time,
            "_end_time": end_time,
            "_frame_count": len(frames),
            "_object_counts": dict(object_counter.most_common(10)),
        }

    def _generate_step_name(self, objects: list[str], index: int) -> str:
        """Generate a human-readable step name from detected objects."""
        if not objects:
            return f"步骤 {index + 1}"

        # Common object → action mappings
        action_map = {
            "person": "操作",
            "hand": "手动",
            "bottle": "使用容器",
            "cup": "使用杯子",
            "bowl": "使用碗",
            "knife": "切割",
            "scissors": "剪切",
            "book": "翻阅",
            "cell phone": "使用手机",
            "laptop": "操作电脑",
            "mouse": "操作鼠标",
            "keyboard": "输入",
            "chair": "调整座椅",
            "dining table": "在桌面操作",
            "tv": "查看屏幕",
            "mouse": "使用鼠标",
        }

        # Remove generic "person" if other objects present
        specific = [o for o in objects if o != "person"]

        if specific:
            primary = specific[0]
            action = action_map.get(primary, f"处理 {primary}")
            return f"{action}"
        elif "person" in objects:
            return f"步骤 {index + 1} - 人工操作"
        else:
            return f"步骤 {index + 1}"

    def _merge_similar_steps(self, steps: list[dict]) -> list[dict]:
        """Merge consecutive steps with same dominant objects."""
        if len(steps) <= 1:
            return steps

        merged = [steps[0]]
        for step in steps[1:]:
            prev = merged[-1]
            prev_set = set(prev.get("expected_objects", []))
            curr_set = set(step.get("expected_objects", []))

            # If objects are the same, merge
            if prev_set == curr_set and prev_set:
                # Extend the previous step
                prev["timeout"] = max(prev["timeout"], step["timeout"]) + step["timeout"]
                prev["estimated_duration"] += step["estimated_duration"]
                prev["_frame_count"] = step.get("_frame_count", 0)
                continue

            merged.append(step)

        # Re-number steps
        for i, step in enumerate(merged):
            step["step_id"] = f"auto_step_{i + 1}"
            step["order"] = i

        return merged
