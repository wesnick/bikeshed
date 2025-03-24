import os
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import FileResponse, HTMLResponse
from psycopg_pool import AsyncConnection
from starlette.status import HTTP_404_NOT_FOUND

from src.dependencies import get_db
from src.models.models import Blob
from src.service.blob_service import BlobService

router = APIRouter(prefix="/blobs", tags=["blobs"])
blob_service = BlobService()

# HTML template for the dropzone upload form
UPLOAD_FORM_HTML = """
<div id="dropzone-container" class="box">
  <form id="upload-form" 
        hx-post="/blobs/upload" 
        hx-encoding="multipart/form-data"
        hx-ext="form-json"
        hx-target="#blob-list"
        hx-swap="afterbegin"
        class="dropzone">
    <div class="dz-message" data-dz-message>
      <span>Drop files here or click to upload</span>
    </div>
    <div class="fallback">
      <input name="file" type="file" multiple />
    </div>
    <input type="hidden" name="description" value="" />
  </form>
</div>
"""

# HTML template for rendering a single blob
BLOB_ITEM_HTML = """
<div class="card mb-3" id="blob-{id}">
  <div class="card-content">
    <div class="media">
      <div class="media-left">
        <figure class="image is-48x48">
          <img src="{thumbnail}" alt="{name}">
        </figure>
      </div>
      <div class="media-content">
        <p class="title is-4">{name}</p>
        <p class="subtitle is-6">{content_type}</p>
      </div>
      <div class="media-right">
        <button class="button is-small is-danger"
                hx-delete="/api/blobs/{id}"
                hx-target="#blob-{id}"
                hx-swap="outerHTML">
          Delete
        </button>
      </div>
    </div>
    <div class="content">
      <p>{description}</p>
      <p><small>{byte_size_formatted} • {created_at}</small></p>
      <a href="{content_url}" class="button is-small is-primary" target="_blank">Download</a>
    </div>
  </div>
</div>
"""


@router.get("/upload-form", response_class=HTMLResponse)
async def get_upload_form():
    """Return the HTML for the dropzone upload form"""
    return UPLOAD_FORM_HTML


@router.get("/", response_model=List[Blob])
async def list_blobs(
    limit: int = 100, 
    offset: int = 0,
    db: AsyncConnection = Depends(get_db)
):
    """List all blobs"""
    return await blob_service.list_blobs(db, limit, offset)


@router.get("/search", response_model=List[Blob])
async def search_blobs(
    q: str,
    limit: int = 20, 
    offset: int = 0,
    db: AsyncConnection = Depends(get_db)
):
    """Search for blobs by name or description"""
    return await blob_service.search_blobs(db, q, limit, offset)


@router.get("/html", response_class=HTMLResponse)
async def list_blobs_html(
    limit: int = 100, 
    offset: int = 0,
    db: AsyncConnection = Depends(get_db)
):
    """List all blobs as HTML for HTMX"""
    blobs = await blob_service.list_blobs(db, limit, offset)
    html = ""
    for blob in blobs:
        # Format the blob size
        if blob.byte_size is not None:
            if blob.byte_size < 1024:
                size_formatted = f"{blob.byte_size} bytes"
            elif blob.byte_size < 1024 * 1024:
                size_formatted = f"{blob.byte_size / 1024:.1f} KB"
            else:
                size_formatted = f"{blob.byte_size / (1024 * 1024):.1f} MB"
        else:
            size_formatted = "Unknown size"
        
        # Get thumbnail URL based on content type
        if blob.content_type.startswith("image/"):
            thumbnail = blob.content_url
        else:
            # Use a generic file icon
            thumbnail = "/static/file-icon.png"
        
        html += BLOB_ITEM_HTML.format(
            id=blob.id,
            name=blob.name,
            description=blob.description or "",
            content_type=blob.content_type,
            byte_size_formatted=size_formatted,
            created_at=blob.created_at.strftime("%Y-%m-%d %H:%M"),
            content_url=blob.content_url,
            thumbnail=thumbnail
        )
    return html


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
async def upload_blob(
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
    
    # Format the blob size
    if blob.byte_size is not None:
        if blob.byte_size < 1024:
            size_formatted = f"{blob.byte_size} bytes"
        elif blob.byte_size < 1024 * 1024:
            size_formatted = f"{blob.byte_size / 1024:.1f} KB"
        else:
            size_formatted = f"{blob.byte_size / (1024 * 1024):.1f} MB"
    else:
        size_formatted = "Unknown size"
    
    # Get thumbnail URL based on content type
    if blob.content_type.startswith("image/"):
        thumbnail = blob.content_url
    else:
        # Use a generic file icon
        thumbnail = "/static/file-icon.png"
    
    return BLOB_ITEM_HTML.format(
        id=blob.id,
        name=blob.name,
        description=blob.description or "",
        content_type=blob.content_type,
        byte_size_formatted=size_formatted,
        created_at=blob.created_at.strftime("%Y-%m-%d %H:%M"),
        content_url=blob.content_url,
        thumbnail=thumbnail
    )


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


@router.delete("/{blob_id}", response_class=HTMLResponse)
async def delete_blob(
    blob_id: UUID,
    db: AsyncConnection = Depends(get_db)
):
    """Delete a blob"""
    success = await blob_service.delete_blob(db, blob_id)
    if not success:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Blob not found")
    return f"<div id='blob-{blob_id}-deleted' hx-swap-oob='true'></div>"
