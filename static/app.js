const authCard = document.getElementById("authCard");
const dashboard = document.getElementById("dashboard");
const signInForm = document.getElementById("signInForm");
const signUpForm = document.getElementById("signUpForm");
const showSignInBtn = document.getElementById("showSignInBtn");
const showSignUpBtn = document.getElementById("showSignUpBtn");
const logoutBtn = document.getElementById("logoutBtn");
const uploadBtn = document.getElementById("uploadBtn");
const fileInput = document.getElementById("fileInput");
const fileList = document.getElementById("fileList");
const toast = document.getElementById("toast");
const welcomeText = document.getElementById("welcomeText");

function setAuthMode(mode) {
  const isSignIn = mode === "signin";
  signInForm.classList.toggle("hidden", !isSignIn);
  signUpForm.classList.toggle("hidden", isSignIn);
  showSignInBtn.classList.toggle("active", isSignIn);
  showSignUpBtn.classList.toggle("active", !isSignIn);
}

function showToast(message, isError = false) {
  toast.textContent = message;
  toast.classList.remove("hidden");
  toast.style.borderColor = isError ? "rgba(255, 107, 107, 0.5)" : "rgba(124, 247, 196, 0.35)";
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.add("hidden"), 2600);
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function formatDate(isoDate) {
  return new Date(isoDate).toLocaleString();
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {})
    },
    ...options
  });

  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) {
    throw new Error(data?.error || "Request failed");
  }
  return data;
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderFiles(files) {
  if (!files.length) {
    fileList.innerHTML = `<p class="hint">No files uploaded yet. Upload your first file to begin building your cloud library.</p>`;
    return;
  }

  fileList.innerHTML = files.map((file) => `
    <article class="file-row">
      <div>
        <h4 class="file-name">${escapeHtml(file.name)}</h4>
        <div class="file-meta">${formatBytes(file.size_bytes)} - ${formatDate(file.uploaded_at)}</div>
        ${file.share_url ? `<div class="share-link">Share link: <a href="${file.share_url}" target="_blank">${location.origin}${file.share_url}</a><br>Expires: ${formatDate(file.share_expires_at)}</div>` : ""}
      </div>
      <div class="file-actions">
        <a href="${file.download_url}"><button type="button">Download</button></a>
        <button class="ghost" type="button" data-share-id="${file.id}">Share</button>
      </div>
    </article>
  `).join("");

  document.querySelectorAll("[data-share-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        const result = await fetchJson(`/api/share/${button.dataset.shareId}`, {
          method: "POST",
          body: "{}"
        });
        await loadFiles();
        await navigator.clipboard.writeText(`${location.origin}${result.share_url}`);
        showToast("Share link created and copied.");
      } catch (error) {
        showToast(error.message, true);
      }
    });
  });
}

async function loadFiles() {
  const files = await fetchJson("/api/files");
  renderFiles(files);
}

async function checkSession() {
  try {
    const me = await fetchJson("/api/me", { headers: {} });
    if (me.authenticated) {
      welcomeText.textContent = `${me.username}'s Drive`;
      authCard.classList.add("hidden");
      dashboard.classList.remove("hidden");
      await loadFiles();
    } else {
      authCard.classList.remove("hidden");
      dashboard.classList.add("hidden");
    }
  } catch {
    authCard.classList.remove("hidden");
    dashboard.classList.add("hidden");
  }
}

signInForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(signInForm);
  try {
    const result = await fetchJson("/api/login", {
      method: "POST",
      body: JSON.stringify({
        username: formData.get("username"),
        password: formData.get("password")
      })
    });
    welcomeText.textContent = `${result.username}'s Drive`;
    authCard.classList.add("hidden");
    dashboard.classList.remove("hidden");
    signInForm.reset();
    await loadFiles();
    showToast("Signed in successfully.");
  } catch (error) {
    showToast(error.message, true);
  }
});

signUpForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(signUpForm);
  try {
    const result = await fetchJson("/api/signup", {
      method: "POST",
      body: JSON.stringify({
        username: formData.get("username"),
        password: formData.get("password"),
        confirm_password: formData.get("confirm_password")
      })
    });
    welcomeText.textContent = `${result.username}'s Drive`;
    authCard.classList.add("hidden");
    dashboard.classList.remove("hidden");
    signUpForm.reset();
    await loadFiles();
    showToast("Account created successfully.");
  } catch (error) {
    showToast(error.message, true);
  }
});

logoutBtn.addEventListener("click", async () => {
  await fetchJson("/api/logout", { method: "POST", body: "{}" });
  dashboard.classList.add("hidden");
  authCard.classList.remove("hidden");
  fileList.innerHTML = "";
  setAuthMode("signin");
  showToast("Signed out successfully.");
});

showSignInBtn.addEventListener("click", () => setAuthMode("signin"));
showSignUpBtn.addEventListener("click", () => setAuthMode("signup"));

uploadBtn.addEventListener("click", async () => {
  const file = fileInput.files[0];
  if (!file) {
    showToast("Choose a file before uploading.", true);
    return;
  }

  try {
    const buffer = await file.arrayBuffer();
    const bytes = new Uint8Array(buffer);
    let binary = "";
    bytes.forEach((byte) => {
      binary += String.fromCharCode(byte);
    });

    await fetchJson("/api/upload", {
      method: "POST",
      body: JSON.stringify({
        filename: file.name,
        content_type: file.type || "application/octet-stream",
        content_base64: btoa(binary)
      })
    });

    fileInput.value = "";
    await loadFiles();
    showToast("File uploaded successfully.");
  } catch (error) {
    showToast(error.message, true);
  }
});

setAuthMode("signin");
checkSession();
