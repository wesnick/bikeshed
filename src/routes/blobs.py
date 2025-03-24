import os
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import FileResponse, HTMLResponse
from psycopg_pool import AsyncConnection
from starlette.status import HTTP_404_NOT_FOUND

from src.dependencies import get_db, get_jinja
from src.models.models import Blob
from src.service.blob_service import BlobService

router = APIRouter(prefix="/blobs", tags=["blobs"])
blob_service = BlobService()
jinja = get_jinja()

@router.get("/", response_class=HTMLResponse)
@jinja.hx('components/blobs/blobs_page.html.j2')
async def get_blobs_page(
    request: Request,
    limit: int = 100, 
    offset: int = 0,
    db: AsyncConnection = Depends(get_db)
):
    """Get the blobs page"""
    blobs = await blob_service.list_blobs(db, limit, offset)
    return {"request": request, "blobs": blobs}

@router.get("/upload", response_class=HTMLResponse)
@jinja.hx('components/blobs/upload_form.html.j2')
async def get_upload_form(request: Request):
    """Return the upload form page"""
    return {"request": request}


@router.get("/api", response_model=List[Blob])
async def list_blobs_api(
    limit: int = 100, 
    offset: int = 0,
    db: AsyncConnection = Depends(get_db)
):
    """List all blobs (API endpoint)"""
    return await blob_service.list_blobs(db, limit, offset)


@router.get("/search", response_model=List[Blob])
async def search_blobs_api(
    q: str,
    limit: int = 20, 
    offset: int = 0,
    db: AsyncConnection = Depends(get_db)
):
    """Search for blobs by name or description (API endpoint)"""
    return await blob_service.search_blobs(db, q, limit, offset)


@router.get("/list-html", response_class=HTMLResponse)
@jinja.hx('components/blobs/blob_list.html.j2')
async def list_blobs_html(
    request: Request,
    limit: int = 100, 
    offset: int = 0,
    db: AsyncConnection = Depends(get_db)
):
    """List all blobs as HTML for HTMX"""
    blobs = await blob_service.list_blobs(db, limit, offset)
    return {"request": request, "blobs": blobs}


@router.get("/search-html", response_class=HTMLResponse)
@jinja.hx('components/blobs/blob_list.html.j2')
async def search_blobs_html(
    request: Request,
    q: str,
    limit: int = 20, 
    offset: int = 0,
    db: AsyncConnection = Depends(get_db)
):
    """Search for blobs as HTML for HTMX"""
    blobs = await blob_service.search_blobs(db, q, limit, offset)
    return {"request": request, "blobs": blobs}


@router.post("/", response_model=Blob)
async def create_blob(
    name: str,
    content_type: str,
    file: UploadFile = File(...),
    description: Optional[str] = None,
    db: AsyncConnection = Depends(get_db)
):
    """Create a new blob"""
    return await blob_service.create_blob_from_upload(
        conn=db,
        upload_file=file,
        description=description
    )


@router.post("/upload", response_class=HTMLResponse)
@jinja.hx('components/blobs/blob_item.html.j2')
async def upload_blob(
    request: Request,
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    db: AsyncConnection = Depends(get_db)
):
    """Upload a blob and return HTML for HTMX"""
    blob = await blob_service.create_blob_from_upload(
        conn=db,
        upload_file=file,
        description=description
    )
    
    return {"request": request, "blob": blob}


@router.get("/{blob_id}", response_model=Blob)
async def get_blob(
    blob_id: UUID,
    db: AsyncConnection = Depends(get_db)
):
    """Get a blob by ID"""
    blob = await blob_service.get_blob(db, blob_id)
    if not blob:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Blob not found")
    return blob


@router.get("/{blob_id}/content")
async def get_blob_content(
    blob_id: UUID,
    db: AsyncConnection = Depends(get_db)
):
    """Get a blob's content"""
    blob = await blob_service.get_blob(db, blob_id)
    if not blob:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Blob not found")
    
    file_path = blob_service.get_blob_content_path(blob_id)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Blob content not found")
    
    return FileResponse(
        path=file_path,
        media_type=blob.content_type,
        filename=blob.name
    )


@router.delete("/api/blobs/{blob_id}", response_class=HTMLResponse)
async def delete_blob(
    blob_id: UUID,
    db: AsyncConnection = Depends(get_db)
):
    """Delete a blob"""
    success = await blob_service.delete_blob(db, blob_id)
    if not success:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Blob not found")
    return f"<div id='blob-{blob_id}-deleted' hx-swap-oob='true'></div>"
