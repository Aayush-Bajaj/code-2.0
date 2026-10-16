"""Optional Ultralytics YOLO inference for machinery/vehicle bounding boxes."""

from pathlib import Path
from typing import List, Optional, Tuple
from PIL import Image
from backend.schemas import BoundingBox

try:
    from ultralytics import YOLO
    _YOLO_AVAILABLE = True
except Exception:
    YOLO = None
    _YOLO_AVAILABLE = False

_YOLO_MODEL = None


def get_yolo_model():
    global _YOLO_MODEL
    if not _YOLO_AVAILABLE:
        return None
    if _YOLO_MODEL is None:
        try:
            _YOLO_MODEL = YOLO("yolov8n.pt")
        except Exception:
            _YOLO_MODEL = None
    return _YOLO_MODEL


def annotate_frame_with_yolo(
    image_input,
    output_path: Optional[Path] = None,
) -> Tuple[Optional[BoundingBox], Optional[Path]]:
    """
    Run pretrained YOLO on a frame to detect vehicles/trucks/machinery.
    Returns (first_bounding_box, annotated_frame_path) if available, or (None, None).
    Gracefully skips if YOLO is unavailable, blocked, or slow.
    """
    model = get_yolo_model()
    if model is None or image_input is None:
        return None, None

    try:
        results = model.predict(source=image_input, verbose=False)
        if not results:
            return None, None

        first_res = results[0]
        boxes = first_res.boxes
        if boxes is None or len(boxes) == 0:
            return None, None

        box = boxes[0]
        xyxy = box.xyxy[0].tolist()
        bbox = BoundingBox(
            x_min=float(xyxy[0]),
            y_min=float(xyxy[1]),
            x_max=float(xyxy[2]),
            y_max=float(xyxy[3]),
        )

        annotated_path = None
        if output_path:
            # Pillow image save for annotated plot
            im_array = first_res.plot()
            im = Image.fromarray(im_array)
            im.save(str(output_path))
            annotated_path = output_path

        return bbox, annotated_path
    except Exception:
        return None, None
