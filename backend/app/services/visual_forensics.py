
import cv2
import numpy as np
from PIL import Image, ImageChops
from io import BytesIO


def analyze_image_bytes(image_bytes: bytes) -> dict:
    """
    Inspect an image for possible visual anomalies.

    This is a heuristic screening tool, not proof of manipulation.
    It reports suspicious regions only when the checks produce
    candidate areas for review.
    """
    try:
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        rgb = np.array(image)
    except Exception as exc:
        raise ValueError("Invalid or corrupted image file.") from exc

    height, width = rgb.shape[:2]

    if width < 32 or height < 32:
        raise ValueError("Image is too small for visual analysis.")

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

    # Compare local texture against a blurred background.
    blurred = cv2.GaussianBlur(gray, (0, 0), 5)
    residual = cv2.absdiff(gray, blurred)

    # Identify areas with unusually strong local residuals.
    threshold = max(
        18,
        int(np.mean(residual) + 2.5 * np.std(residual)),
    )
    _, mask = cv2.threshold(
        residual,
        threshold,
        255,
        cv2.THRESH_BINARY,
    )

    # Merge nearby candidate pixels into larger regions.
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        kernel,
    )

    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    regions = []

    minimum_area = max(100, int(width * height * 0.001))

    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = w * h

        if area < minimum_area:
            continue

        # Avoid treating a large fraction of the whole image
        # as a meaningful localized candidate.
        if area > width * height * 0.5:
            continue

        regions.append({
            "x": int(x),
            "y": int(y),
            "width": int(w),
            "height": int(h),
            "area": int(area),
            "reason": (
                "Unusually strong local pixel differences; "
                "manual review is required."
            ),
        })

    # Create a normalized heatmap for visual inspection.
    heatmap = cv2.applyColorMap(
        cv2.normalize(
            residual,
            None,
            0,
            255,
            cv2.NORM_MINMAX,
        ),
        cv2.COLORMAP_JET,
    )

    # OpenCV returns BGR; convert to RGB for Pillow.
    heatmap_rgb = cv2.cvtColor(
        heatmap,
        cv2.COLOR_BGR2RGB,
    )

    heatmap_image = Image.fromarray(heatmap_rgb)
    output = BytesIO()
    heatmap_image.save(output, format="PNG")

    return {
        "image_width": width,
        "image_height": height,
        "regions": regions,
        "heatmap_png": output.getvalue(),
        "message": (
            "Potential manipulation detected."
            if regions
            else "No candidate regions were detected by this heuristic. "
                 "This does not establish authenticity."
        ),
    }