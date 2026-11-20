"""Keep uploaded files (product images, attachments) in S3-compatible object storage.

Storage is on when the site has S3 credentials, read from site_config.json (``s3_access_key``,
``s3_secret_key``, ``s3_url``) or from the environment (``S3_ACCESS_KEY``, ``S3_SECRET_KEY``,
``S3_URL``). ``s3_url`` is the bucket's own address, e.g. ``https://hatix.nbg1.your-objectstorage.com``
for the Hetzner bucket ``hatix`` in ``nbg1``. Set ``s3_bucket`` (and ``s3_region``) as well to use a
plain endpoint address instead. Without credentials, files stay on the server disk as before.

Frappe's ``write_file`` and ``delete_file_data_content`` hooks store and remove the content. The
File keeps a ``/api/method/hat.storage.file?key=...`` URL, which Frappe treats as a remote file. That
method checks the File's permissions like Frappe does for /private/files and redirects to a
short-lived signed S3 link, so the bucket itself stays private. Files already on disk keep working.
"""

import os
import re
from functools import lru_cache
from urllib.parse import quote, urlsplit

import frappe
from frappe import _
from frappe.core.doctype.file.file import FILE_ENCODING_OPTIONS, OLE_FILE_SIGNATURE, File
from frappe.core.doctype.file.utils import find_file_by_url
from frappe.utils.response import FORCE_DOWNLOAD_EXTENSIONS

FILE_URL_PREFIX = "/api/method/hat.storage.file?key="
# How long a signed link works after the redirect.
PUBLIC_LINK_SECONDS = 6 * 3600
PRIVATE_LINK_SECONDS = 10 * 60
UNSAFE_KEY_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def get_config() -> frappe._dict | None:
	def value(name: str) -> str | None:
		return frappe.conf.get(f"s3_{name}") or os.environ.get(f"S3_{name.upper()}")

	access_key, secret_key, url = value("access_key"), value("secret_key"), value("url")
	if not (access_key and secret_key and url):
		return None

	host = urlsplit(url if "://" in url else f"https://{url}").netloc
	bucket = value("bucket")
	if not bucket:
		# Bucket address: <bucket>.<endpoint host>
		bucket, host = host.split(".", 1)
	return frappe._dict(
		access_key=access_key,
		secret_key=secret_key,
		bucket=bucket,
		endpoint_url=f"https://{host}",
		# Hetzner: nbg1.your-objectstorage.com is in region nbg1
		region=value("region") or host.split(".", 1)[0],
	)


def is_enabled() -> bool:
	return bool(get_config())


@lru_cache(maxsize=4)
def _client(access_key: str, secret_key: str, endpoint_url: str, region: str):
	import boto3
	from botocore.config import Config

	return boto3.client(
		"s3",
		endpoint_url=endpoint_url,
		region_name=region,
		aws_access_key_id=access_key,
		aws_secret_access_key=secret_key,
		config=Config(
			signature_version="s3v4",
			s3={"addressing_style": "virtual"},
			# S3-compatible stores (Ceph at Hetzner) reject the newer default checksum headers
			request_checksum_calculation="when_required",
			response_checksum_validation="when_required",
			retries={"max_attempts": 3, "mode": "standard"},
		),
	)


def get_client(config: frappe._dict | None = None):
	config = config or get_config()
	if not config:
		frappe.throw(_("S3 file storage is not configured"))
	return _client(config.access_key, config.secret_key, config.endpoint_url, config.region)


def get_key(file_url: str | None) -> str | None:
	if file_url and file_url.startswith(FILE_URL_PREFIX):
		return file_url[len(FILE_URL_PREFIX) :]
	return None


def make_key(file_name: str) -> str:
	# One folder per site, so several sites can share a bucket; the random part keeps names unique.
	site = UNSAFE_KEY_CHARS.sub("-", frappe.local.site)
	name = re.sub(r"-+(?=\.)", "", UNSAFE_KEY_CHARS.sub("-", file_name)).strip("-.") or "file"
	return f"{site}/files/{frappe.generate_hash(length=12)}/{name}"


# Hooks


def write_file(file: File) -> dict:
	"""`write_file` hook: upload a new File's content instead of writing it to disk."""
	config = get_config()
	if not config:
		return file.save_file_on_filesystem()

	content = file._content
	if isinstance(content, str):
		content = content.encode()
	if hasattr(file, "check_content"):  # Frappe 17: refuses PDFs with JavaScript
		file._content = content
		file.check_content()

	key = make_key(file.file_name)
	get_client(config).put_object(
		Bucket=config.bucket,
		Key=key,
		Body=content,
		ContentType=file.content_type or "application/octet-stream",
	)
	file.file_url = FILE_URL_PREFIX + key
	return {"file_name": file.file_name, "file_url": file.file_url}


def delete_file_data_content(file: File, only_thumbnail: bool = False) -> None:
	"""`delete_file_data_content` hook: remove the stored content when its last File goes."""
	key = get_key(file.file_url)
	if not key:
		file.delete_file_from_filesystem(only_thumbnail=only_thumbnail)
		return

	if file.thumbnail_url:
		from frappe.core.doctype.file.utils import delete_file

		delete_file(file.thumbnail_url)
	if not only_thumbnail:
		config = get_config()
		if config:
			get_client(config).delete_object(Bucket=config.bucket, Key=key)
		else:
			frappe.log_error(f"S3 storage is not configured; {key} was left in the bucket", "S3 storage")


class HATFile(File):
	"""File that can also read its content back from S3 (emails, print attachments, unzip)."""

	def exists_on_disk(self):
		if get_key(self.file_url):
			return True
		return super().exists_on_disk()

	def get_content(self, encodings=None) -> bytes | str:
		key = get_key(self.file_url)
		if not key or self.get("content"):
			return super().get_content(encodings)

		import filetype

		config = get_config()
		content = get_client(config).get_object(Bucket=config.bucket, Key=key)["Body"].read()
		# Same as Frappe does for files on disk: text comes back as str, anything else as bytes
		if not filetype.guess(content) and not content.startswith(OLE_FILE_SIGNATURE):
			for encoding in encodings or FILE_ENCODING_OPTIONS:
				try:
					content = content.decode(encoding)
					break
				except UnicodeDecodeError:
					continue
		self._content = content
		return self._content


# Serving


@frappe.whitelist(allow_guest=True, methods=["GET"])
def file(key: str) -> None:
	"""Redirect to a signed link for a stored file the user may see."""
	from werkzeug.exceptions import Forbidden, NotFound

	file_url = FILE_URL_PREFIX + key
	files = frappe.get_all("File", filters={"file_url": file_url}, fields=["name", "is_private", "file_name"])
	if not files:
		raise NotFound(_("File not found"))

	found = next((f for f in files if not f.is_private), None)
	if not found:
		if frappe.session.user == "Guest":
			raise Forbidden(_("You don't have permission to access this file"))
		found = find_file_by_url(file_url)
		if not found:
			raise Forbidden(_("You don't have permission to access this file"))

	seconds = PRIVATE_LINK_SECONDS if found.is_private else PUBLIC_LINK_SECONDS
	file_name = found.file_name or key.rsplit("/", 1)[-1]
	disposition = "attachment" if file_name.lower().endswith(FORCE_DOWNLOAD_EXTENSIONS) else "inline"
	ascii_name = file_name.encode("ascii", "replace").decode().replace('"', "").replace("\\", "")

	config = get_config()
	if not config:
		raise NotFound(_("File storage is not available"))
	link = get_client(config).generate_presigned_url(
		"get_object",
		Params={
			"Bucket": config.bucket,
			"Key": key,
			"ResponseContentDisposition": (
				f"{disposition}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(file_name)}"
			),
		},
		ExpiresIn=seconds,
	)
	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = link
