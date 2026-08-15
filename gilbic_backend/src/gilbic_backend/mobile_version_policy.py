from __future__ import annotations

from dataclasses import dataclass
import re

from .config import Settings


_VERSION_RE = re.compile(r"^(?P<release>\d+(?:\.\d+){0,3})(?:\+(?P<build>\d+))?$")


class UnsupportedMobileAppVersion(RuntimeError):
    """The calling Android/iOS build cannot satisfy the configured minimum."""


class InvalidMobileVersionPolicy(RuntimeError):
    """The server-side minimum-version configuration is invalid."""


@dataclass(frozen=True, order=True, slots=True)
class ParsedMobileVersion:
    release: tuple[int, int, int, int]
    build: int


def parse_mobile_version(value: str) -> ParsedMobileVersion:
    normalized = value.strip()
    match = _VERSION_RE.fullmatch(normalized)
    if match is None:
        raise ValueError(f"Invalid mobile version: {value!r}")

    release_parts = [int(part) for part in match.group("release").split(".")]
    release_parts.extend([0] * (4 - len(release_parts)))
    build = int(match.group("build") or 0)
    return ParsedMobileVersion(tuple(release_parts), build)


def _configured_minimum(settings: Settings, platform: str) -> str:
    if platform == "android":
        return settings.mobile_android_minimum_version.strip()
    if platform == "ios":
        return settings.mobile_ios_minimum_version.strip()
    return ""


def _has_mobile_minimum(settings: Settings) -> bool:
    return bool(
        settings.mobile_android_minimum_version.strip()
        or settings.mobile_ios_minimum_version.strip()
    )


def enforce_mobile_app_version(
    *,
    platform: str | None,
    app_version: str | None,
    settings: Settings,
) -> None:
    """Fail closed for a configured Android/iOS minimum version.

    When no minimum is configured, existing development/test clients remain
    compatible. Once either mobile minimum is configured, callers on a mobile
    auth route must identify an Android/iOS platform so an older client cannot
    bypass the policy simply by omitting its platform/version metadata.
    """

    normalized_platform = (platform or "").strip().lower()
    if normalized_platform not in {"android", "ios"}:
        if _has_mobile_minimum(settings):
            raise UnsupportedMobileAppVersion(
                "This Gilbic mobile build cannot be verified. Update the app before continuing."
            )
        return

    minimum = _configured_minimum(settings, normalized_platform)
    if not minimum:
        return

    try:
        minimum_version = parse_mobile_version(minimum)
    except ValueError as exc:
        raise InvalidMobileVersionPolicy(
            f"Invalid minimum version configured for {normalized_platform}."
        ) from exc

    current_text = (app_version or "").strip()
    try:
        current_version = parse_mobile_version(current_text)
    except ValueError as exc:
        raise UnsupportedMobileAppVersion(
            "This Gilbic mobile build cannot be verified. Update the app before continuing."
        ) from exc

    if current_version < minimum_version:
        platform_name = "Android" if normalized_platform == "android" else "iOS"
        raise UnsupportedMobileAppVersion(
            f"This Gilbic {platform_name} version is no longer supported. "
            f"Update to version {minimum} or later before continuing."
        )
