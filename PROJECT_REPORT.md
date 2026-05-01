# Cloud-Based File Storage System (Mini Google Drive)

## Objective

The objective of this project is to design and develop a cloud-based file storage system that allows users to securely upload, store, access, download, and share files over the internet using cloud-style infrastructure.

## Project Overview

This application is a simplified version of a cloud storage service. Users interact through a web interface, while a backend server processes requests and a storage layer manages uploaded files. Instead of tightly coupling files to the local machine, the project uses a dedicated storage abstraction to represent cloud-backed storage behavior.

The project demonstrates how cloud computing supports scalability, accessibility, and reliability in file management systems.

## System Architecture

### 1. Frontend Layer

- Provides a web interface for users
- Supports:
  - Login
  - File upload
  - Viewing stored files
  - File download
  - File sharing

### 2. Backend Layer

- Handles application logic
- Processes:
  - Authentication requests
  - File uploads and downloads
  - Communication with the storage layer
  - Share-link generation

### 3. Cloud Storage Layer

- Stores files in a dedicated storage area
- Implemented through the `CloudStorage` service
- Designed so it can be replaced by Firebase Storage or Amazon S3 in a future upgrade
- Provides:
  - Organized object storage
  - Reliability
  - Scalable architecture design

### 4. Database Layer

- Stores metadata such as:
  - Username
  - File names
  - Upload timestamps
  - File size
  - Share-link expiry
- Implemented with SQLite for the current version

## Working Flow

1. The user opens the application in a browser.
2. The user logs in using credentials.
3. After authentication, the dashboard becomes available.
4. The user uploads a file.
5. The backend sends the file to the storage layer.
6. The storage layer stores the file and returns a stored object key.
7. Metadata is saved in the database.
8. The user can view files, download them, or generate a shareable link.

## Features

### File Upload

Users can upload files from their system to the storage layer.

### File Download

Users can retrieve stored files whenever needed.

### File Sharing

The system generates a secure temporary link that can be shared with others.

### User Authentication

Only authorized users can access their own dashboard and stored files.

### Cloud Storage Integration

The application uses a cloud-style storage architecture through an abstraction layer, making it suitable for future migration to Firebase or AWS.

## Role of Cloud Computing

This project uses cloud computing concepts to:

- Store large amounts of data without depending on direct local file handling in the UI
- Provide access from any location through a browser
- Support scalability through a replaceable storage layer
- Improve reliability through structured storage and metadata management

## Security Considerations

- Session-based authentication
- User-specific access control for private files
- Temporary share links with expiry
- File-name sanitization
- Controlled upload-size limit in the current version

## Conclusion

This project demonstrates how cloud computing concepts can be applied to build a scalable and efficient file storage system. By integrating a frontend, backend, storage service, and metadata database, the application provides secure file management features similar to modern cloud-drive platforms. The current version is fully runnable as a local application and can be extended to real cloud services such as Firebase Storage or Amazon S3.
