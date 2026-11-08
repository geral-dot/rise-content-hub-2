"""RISE editorial policy: dependency-free rules for approval of post version."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ApprovalState:
    version: int
    copy_approved: bool = False
    visual_approved: bool = False

    def __post_init__(self):
        if self.version < 1:
            raise ValueError("A versão deve ser positiva")

    def change_version(self, new_version: int) -> "ApprovalState":
        if new_version <= self.version:
            raise ValueError("A alteração tem de gerar uma versão superior")
        return ApprovalState(version=new_version)

    def decision(self, version: int, component: str, approved: bool) -> "ApprovalState":
        if version != self.version:
            raise ValueError("Aprovação obsoleta: a versão foi alterada")
        if component not in ("copy", "visual"):
            raise ValueError("Componente inválida")
        values = {"copy_approved": self.copy_approved, "visual_approved": self.visual_approved}
        values[component + "_approved"] = bool(approved)
        return ApprovalState(version=self.version, **values)

    def can_publish(self, has_copy: bool, has_visual: bool) -> bool:
        return bool(has_copy and has_visual and self.copy_approved and self.visual_approved)
