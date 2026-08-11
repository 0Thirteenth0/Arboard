from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageCms


ICC_MODES = ("Off", "Convert", "Embed only")
RENDERING_INTENTS = (
    "Perceptual",
    "Relative Colorimetric",
    "Saturation",
    "Absolute Colorimetric",
)

_INTENT_VALUES = {
    "Perceptual": ImageCms.Intent.PERCEPTUAL,
    "Relative Colorimetric": ImageCms.Intent.RELATIVE_COLORIMETRIC,
    "Saturation": ImageCms.Intent.SATURATION,
    "Absolute Colorimetric": ImageCms.Intent.ABSOLUTE_COLORIMETRIC,
}


@dataclass(frozen=True)
class EmbeddedProfileInfo:
    data: bytes
    name: str
    color_space: str


@dataclass
class PreparedColorManagement:
    mode: str
    output_mode: str
    profile_bytes: bytes | None = None
    profile_name: str = ""
    input_profile_name: str = "sRGB working space"
    transform: object | None = None

    def apply(self, image: Image.Image) -> Image.Image:
        if self.transform is None:
            if image.mode != self.output_mode:
                return image.convert(self.output_mode)
            return image
        if image.mode != "RGB":
            image = image.convert("RGB")
        return ImageCms.applyTransform(image, self.transform)


def normalize_icc_mode(value: str) -> str:
    text = str(value or "Off").strip().casefold()
    if text == "convert":
        return "Convert"
    if text in {"embed", "embed only", "assign"}:
        return "Embed only"
    return "Off"


def normalize_rendering_intent(value: str) -> str:
    text = str(value or "Perceptual").strip().casefold()
    for intent in RENDERING_INTENTS:
        if text == intent.casefold():
            return intent
    return "Perceptual"


def _profile_details(profile) -> tuple[str, str]:
    cms_profile = getattr(profile, "profile", profile)
    color_space = str(getattr(cms_profile, "xcolor_space", "")).strip().upper()
    try:
        name = ImageCms.getProfileName(profile).strip()
    except Exception:
        name = "ICC profile"
    return name, color_space


def detect_embedded_icc(source_path: Path) -> EmbeddedProfileInfo | None:
    if Path(source_path).suffix.lower() not in {".jpg", ".jpeg", ".png", ".tif", ".tiff"}:
        return None
    try:
        with Image.open(source_path) as image:
            data = image.info.get("icc_profile")
        if not data:
            return None
        profile = ImageCms.ImageCmsProfile(BytesIO(bytes(data)))
        name, color_space = _profile_details(profile)
        return EmbeddedProfileInfo(bytes(data), name, color_space)
    except Exception:
        return None


def prepare_color_management(
    *,
    source_path: Path,
    color_mode: str,
    icc_mode: str,
    output_profile_path: str,
    rendering_intent: str,
) -> PreparedColorManagement:
    mode = normalize_icc_mode(icc_mode)
    output_mode = "CMYK" if str(color_mode).upper() == "CMYK" else "RGB"
    if mode == "Off":
        return PreparedColorManagement(mode=mode, output_mode=output_mode)

    profile_path = Path(output_profile_path).expanduser()
    if not output_profile_path.strip() or not profile_path.is_file():
        raise ValueError("Choose a valid output ICC profile, or set ICC Handling to Off.")
    try:
        output_profile = ImageCms.getOpenProfile(str(profile_path))
        output_bytes = profile_path.read_bytes()
    except Exception as exc:
        raise ValueError(f"Could not open output ICC profile: {profile_path}") from exc
    output_name, output_space = _profile_details(output_profile)
    if output_space != output_mode:
        raise ValueError(
            f"The selected ICC profile is {output_space or 'an unknown color space'}, "
            f"but Color Mode is {output_mode}."
        )

    prepared = PreparedColorManagement(
        mode=mode,
        output_mode=output_mode,
        profile_bytes=output_bytes,
        profile_name=output_name,
    )
    if mode == "Embed only":
        return prepared

    embedded = detect_embedded_icc(source_path)
    input_profile = None
    if embedded and embedded.color_space == "RGB":
        try:
            input_profile = ImageCms.ImageCmsProfile(BytesIO(embedded.data))
            prepared.input_profile_name = embedded.name
        except Exception:
            input_profile = None
    if input_profile is None:
        input_profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))

    intent_name = normalize_rendering_intent(rendering_intent)
    try:
        prepared.transform = ImageCms.buildTransformFromOpenProfiles(
            input_profile,
            output_profile,
            "RGB",
            output_mode,
            renderingIntent=_INTENT_VALUES[intent_name],
        )
    except Exception as exc:
        raise ValueError(
            f"Could not build the ICC conversion from {prepared.input_profile_name} to {output_name}."
        ) from exc
    return prepared
