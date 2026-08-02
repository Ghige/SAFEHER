from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from app.db.session import get_db
from app.api.deps import get_current_user, get_verified_user
from app.models.user import User
from app.models.helper import Helper
from app.models.alert import Alert
from app.models.blocklist import Blocklist
from app.schemas.helper_schema import HelperResponse, BlocklistCreate, BlocklistResponse
from app.services.helper_service import approve_helper, helper_respond, block_helper

router = APIRouter(prefix="/helpers", tags=["Helpers"])


@router.get("/nearby", response_model=list[HelperResponse])
def get_nearby_helpers(
    alert_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of helpers notified for this alert."""
    alert = db.query(Alert).filter(
        Alert.id == alert_id,
        Alert.user_id == current_user.id,
    ).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    helpers = db.query(Helper).filter(Helper.alert_id == alert_id).all()

    result = []
    for h in helpers:
        helper_user = db.query(User).filter(User.id == h.helper_user_id).first()
        resp = HelperResponse(
            id=h.id,
            alert_id=h.alert_id,
            status=h.status,
            notified_at=h.notified_at,
            identity_revealed=h.identity_revealed,
            approved_by_user=h.approved_by_user,
            # Only reveal identity if user approved
            name=helper_user.name if h.identity_revealed and helper_user else None,
            phone_number=helper_user.phone_number if h.identity_revealed and helper_user else None,
        )
        result.append(resp)
    return result


@router.post("/approve/{helper_id}", response_model=HelperResponse)
def approve(
    helper_id: UUID,
    current_user: User = Depends(get_verified_user),
    db: Session = Depends(get_db)
):
    """User approves a helper — reveals their identity."""
    try:
        h = approve_helper(db, helper_id, current_user.id)
        helper_user = db.query(User).filter(User.id == h.helper_user_id).first()
        return HelperResponse(
            id=h.id, alert_id=h.alert_id, status=h.status,
            notified_at=h.notified_at, identity_revealed=h.identity_revealed,
            approved_by_user=h.approved_by_user,
            name=helper_user.name if helper_user else None,
            phone_number=helper_user.phone_number if helper_user else None,
        )
    except ValueError as e:
        if str(e) == "Unauthorized":
            raise HTTPException(status_code=403, detail=str(e))
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/block/{helper_id}", status_code=204)
def block(
    helper_id: UUID,
    current_user: User = Depends(get_verified_user),
    db: Session = Depends(get_db)
):
    """Block a helper from this alert."""
    try:
        block_helper(db, helper_id, current_user.id)
    except ValueError as e:
        if str(e) == "Unauthorized":
            raise HTTPException(status_code=403, detail=str(e))
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/respond/{alert_id}", response_model=HelperResponse)
def respond(
    alert_id: UUID,
    current_user: User = Depends(get_verified_user),
    db: Session = Depends(get_db)
):
    """Helper says they are on their way."""
    try:
        h = helper_respond(db, alert_id, current_user.id)
        helper_user = db.query(User).filter(User.id == h.helper_user_id).first()
        return HelperResponse(
            id=h.id,
            alert_id=h.alert_id,
            status=h.status,
            notified_at=h.notified_at,
            identity_revealed=h.identity_revealed,
            approved_by_user=h.approved_by_user,
            name=helper_user.name if h.identity_revealed and helper_user else None,
            phone_number=helper_user.phone_number if h.identity_revealed and helper_user else None,
        )
    except ValueError as e:
        if str(e) == "Unauthorized":
            raise HTTPException(status_code=403, detail=str(e))
        raise HTTPException(status_code=404, detail=str(e))


# ── Blocklist ──────────────────────────────────────────────────────────────────

@router.get("/blocklist", response_model=list[BlocklistResponse])
def get_blocklist(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(Blocklist).filter(Blocklist.user_id == current_user.id).all()


@router.post("/blocklist", response_model=BlocklistResponse, status_code=201)
def add_to_blocklist(
    payload: BlocklistCreate,
    current_user: User = Depends(get_verified_user),
    db: Session = Depends(get_db)
):
    entry = Blocklist(user_id=current_user.id, blocked_phone=payload.blocked_phone)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/blocklist/{entry_id}", status_code=204)
def remove_from_blocklist(
    entry_id: UUID,
    current_user: User = Depends(get_verified_user),
    db: Session = Depends(get_db)
):
    entry = db.query(Blocklist).filter(
        Blocklist.id == entry_id,
        Blocklist.user_id == current_user.id
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(entry)
    db.commit()
