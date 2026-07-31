from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RequestContext:
    user_id: UUID | None = None
    negocio_id: UUID | None = None
    role: str | None = None
    route_id: UUID | None = None
    device_id: UUID | None = None

    def is_admin(self) -> bool:
        return self.role == "ADMINISTRADOR"

    def is_cobrador(self) -> bool:
        return self.role == "COBRADOR"

    def has_negocio(self, negocio_id: UUID) -> bool:
        return self.negocio_id is not None and self.negocio_id == negocio_id

    def has_route(self, route_id: UUID) -> bool:
        return self.route_id is not None and self.route_id == route_id

    def to_dict(self) -> dict:
        return {
            "user_id": str(self.user_id) if self.user_id else None,
            "negocio_id": str(self.negocio_id) if self.negocio_id else None,
            "role": self.role,
            "route_id": str(self.route_id) if self.route_id else None,
            "device_id": str(self.device_id) if self.device_id else None,
        }
