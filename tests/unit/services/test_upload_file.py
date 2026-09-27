"""Unit tests for uploading avatars to Cloudinary."""

from io import BytesIO
from unittest.mock import patch

from fastapi import UploadFile

from src.services.upload_file import UploadFileService


def test_upload_file_returns_cropped_url():
    service = UploadFileService("demo-cloud", "key", "secret")
    file = UploadFile(BytesIO(b"image"), filename="avatar.png")

    with patch("cloudinary.uploader.upload", return_value={"version": 123}) as upload:
        url = service.upload_file(file, "alice")

    assert upload.call_args.kwargs == {"public_id": "ContactsApp/alice", "overwrite": True}
    assert url == (
        "https://res.cloudinary.com/demo-cloud/image/upload/"
        "c_fill,h_250,w_250/v123/ContactsApp/alice"
    )
