"""Staff-only configuration in Django admin; client roles never use this page."""
from django.contrib import admin
from .models import RiseBrandProfile, RiseRetainer, RiseApprovalGate, RiseApprovalHistory, RiseLegacySnapshot


@admin.register(RiseBrandProfile)
class RiseBrandProfileAdmin(admin.ModelAdmin):
    list_display = ("workspace", "enforce_dual_approval", "updated_at")
    search_fields = ("workspace__name",)


@admin.register(RiseRetainer)
class RiseRetainerAdmin(admin.ModelAdmin):
    list_display = ("workspace", "period", "posts_included", "stories_included")
    list_filter = ("period",)


@admin.register(RiseApprovalGate)
class RiseApprovalGateAdmin(admin.ModelAdmin):
    list_display = ("post", "content_version", "copy_approved", "visual_approved", "updated_at")
    readonly_fields = ("content_version", "snapshot_digest", "copy_approved", "visual_approved", "updated_at")
    def has_add_permission(self, request):
        return False


@admin.register(RiseApprovalHistory)
class RiseApprovalHistoryAdmin(admin.ModelAdmin):
    list_display = ("post_id_at_decision", "content_version", "component", "approved", "actor", "created_at")
    readonly_fields = ("gate", "post_id_at_decision", "content_version", "snapshot_digest", "component", "approved", "actor", "created_at")
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(RiseLegacySnapshot)
class RiseLegacySnapshotAdmin(admin.ModelAdmin):
    list_display = ("source_table", "source_id", "source_kind", "imported_at")
    readonly_fields = ("source_table", "source_id", "source_client_id", "source_kind", "checksum_sha256", "snapshot", "imported_at")
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False
