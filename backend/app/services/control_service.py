"""System control plane — legacy global kill switch row."""

from sqlalchemy.orm import Session

from app.models import ControlModel
from app.security import now


def get_or_create_control(db: Session) -> ControlModel:
    ctrl = db.query(ControlModel).filter(ControlModel.id == "system_kill_switch").first()
    if not ctrl:
        ctrl = ControlModel(
            id="system_kill_switch",
            enabled=False,
            reason="",
            actor="system",
            updated_at=now(),
        )
        db.add(ctrl)
        db.commit()
        db.refresh(ctrl)
    return ctrl
