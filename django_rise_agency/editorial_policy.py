"""Dependency-free policies shared by the Django integration and portable tests."""

# Authored options that materially change how the audience will see a post.
# Never include provider response IDs/timestamps in the approval fingerprint.
EDITORIAL_PLATFORM_EXTRA_KEYS = frozenset(
    {
        "post_type",
        "privacy_level",
        "board_id",
        "thumbnail_asset_id",
        "cover_image_asset_id",
        "tags",
        "description",
        "disable_comments",
        "is_aigc",
        "audience",
        "category_id",
        "youtube_settings",
    }
)


def editorial_platform_options(platform_extra):
    return {key: value for key, value in (platform_extra or {}).items() if key in EDITORIAL_PLATFORM_EXTRA_KEYS}


def client_can_review(statuses):
    """Clients may only see content explicitly in the client-review stage."""
    return "pending_client" in statuses


def has_approved_components(copy_approved, visual_approved, approved_digest, current_digest):
    return bool(copy_approved and visual_approved and approved_digest and approved_digest == current_digest)
