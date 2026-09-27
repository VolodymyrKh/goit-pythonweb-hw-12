"""Uploading user avatars to Cloudinary."""

import cloudinary
import cloudinary.uploader
import cloudinary.utils
from fastapi import UploadFile


class UploadFileService:
    """Configures Cloudinary and uploads files.

    Args:
        cloud_name: Cloudinary cloud name.
        api_key: Cloudinary API key.
        api_secret: Cloudinary API secret.
    """

    def __init__(self, cloud_name: str, api_key: str, api_secret: str):
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True,
        )

    @staticmethod
    def upload_file(file: UploadFile, username: str) -> str:
        """Upload the avatar to Cloudinary and return a 250x250 cropped image URL.

        A fixed public_id per user means a new upload overwrites the old avatar.
        """
        public_id = f"ContactsApp/{username}"
        result = cloudinary.uploader.upload(
            file.file, public_id=public_id, overwrite=True
        )
        url, _ = cloudinary.utils.cloudinary_url(
            public_id,
            width=250,
            height=250,
            crop="fill",
            version=result.get("version"),
        )
        return url
