# Cloud-Based File Storage System (Mini Google Drive)

This project is a lightweight cloud-drive style web application that demonstrates how a file storage platform can be designed using a frontend layer, backend layer, storage layer, and metadata database.

The implementation in this repository is intentionally dependency-free so it runs easily in a constrained environment. The storage layer currently uses a local disk-backed `CloudStorage` abstraction, which mirrors how a real cloud provider integration would behave. That means the same architecture can later be connected to Firebase Storage or Amazon S3 with minimal controller changes.

## Objective

The system allows users to:

- Log in securely
- Upload files
- View stored files
- Download files
- Generate temporary shareable links

## Architecture

### 1. Frontend Layer

- Built with HTML, CSS, and vanilla JavaScript
- Provides login, upload, file listing, download, and share workflows

### 2. Backend Layer

- Implemented with Python's built-in `http.server`
- Handles authentication, API routing, upload processing, downloads, and share-link generation

### 3. Cloud Storage Layer

- Implemented through [`storage.py`](./storage.py)
- Uses a disk-backed adapter in `data/cloud_storage/`
- Can be swapped with Firebase Storage or Amazon S3 later

### 4. Database Layer

- Uses SQLite in `data/app.db`
- Stores users, file metadata, and share-link expiry data

## Working Flow

1. User opens the app in a browser.
2. User logs in with credentials.
3. The dashboard loads after authentication.
4. User uploads a file.
5. Backend sends the file to the storage layer.
6. Storage returns a stored object key.
7. Metadata is recorded in SQLite.
8. User can view, download, or share the file.

## Features

- File upload
- File download
- Temporary file sharing
- User authentication
- Metadata tracking
- Cloud-style storage abstraction

## Security Considerations

- Authenticated session cookie
- User-scoped file access
- Expiring share links
- Filename sanitization
- File size limit for the current application build

## Run

```powershell
python app.py
```

Then open `http://127.0.0.1:8000`

## Project Structure

```text
.
|-- app.py
|-- storage.py
|-- static/
|   |-- app.js
|   |-- index.html
|   `-- styles.css
`-- data/
```

## Future Cloud Upgrade Ideas

- Replace `CloudStorage` with Firebase Storage SDK integration
- Replace SQLite auth with Firebase Authentication
- Use signed URLs from S3 or Firebase for secure downloads
- Add per-user folders and deletion support
- Add search, file previews, and quota enforcement
