from fastapi import APIRouter

router = APIRouter(prefix="/ping", tags=["Health"])


@router.get("/")
def ping():
    """Health check — also used by dead man's switch monitor."""
    return {"status": "SafeHer backend is running 🛡️"}
