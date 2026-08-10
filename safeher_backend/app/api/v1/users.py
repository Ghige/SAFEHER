from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.contact import EmergencyContact
from app.schemas.user_schema import UserProfile, ContactCreate, ContactResponse, DeviceTokenUpdate

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/profile", response_model=UserProfile)
def get_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/contacts", response_model=list[ContactResponse])
def get_contacts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(EmergencyContact).filter(
        EmergencyContact.user_id == current_user.id
    ).order_by(EmergencyContact.ring_priority).all()


@router.post("/contacts", response_model=ContactResponse, status_code=201)
def add_contact(
    payload: ContactCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Max 5 emergency contacts
    count = db.query(EmergencyContact).filter(
        EmergencyContact.user_id == current_user.id
    ).count()
    if count >= 5:
        raise HTTPException(status_code=400, detail="Maximum 5 emergency contacts allowed")

    contact = EmergencyContact(
        user_id=current_user.id,
        name=payload.name,
        phone_number=payload.phone_number,
        relationship_type=payload.relationship,
        ring_priority=payload.ring_priority,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


@router.delete("/contacts/{contact_id}", status_code=204)
def delete_contact(
    contact_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    contact = db.query(EmergencyContact).filter(
        EmergencyContact.id == contact_id,
        EmergencyContact.user_id == current_user.id
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    db.delete(contact)
    db.commit()


@router.post("/device-token", status_code=204)
def register_device_token(
    payload: DeviceTokenUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Register or update the user's FCM device token for push notifications."""
    current_user.fcm_token = payload.fcm_token.strip()
    db.commit()
