const state = {
  token: null,
  products: [],
  activeProduct: null,
  selectedProducts: new Set(),
};

const overlay = document.getElementById("login-overlay");
const loginForm = document.getElementById("login-form");
const loginError = document.getElementById("login-error");
const logoutBtn = document.getElementById("logout");
const productsTable = document.querySelector("#products-table tbody");
const createProductForm = document.getElementById("create-product");
const detailsContainer = document.getElementById("product-details");
const importWindow = document.getElementById("import-window");
const importForm = document.getElementById("import-form");
const importError = document.getElementById("import-error");
const userWindow = document.getElementById("user-window");
const credentialsForm = document.getElementById("credentials-form");
const credentialsSuccess = document.getElementById("credentials-success");
const credentialsError = document.getElementById("credentials-error");
const batchWindow = document.getElementById("batch-window");
const batchForm = document.getElementById("batch-form");
const batchCount = document.getElementById("batch-count");
const batchError = document.getElementById("batch-error");
const selectAll = document.getElementById("select-all");

function escapeHtml(value) {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function api(path, options = {}) {
  const headers = options.headers || {};
  if (state.token) {
    headers.Authorization = `Bearer ${state.token}`;
  }
  return fetch(path, {
    ...options,
    headers,
  }).then(async (response) => {
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      const error = data.detail || data.message || "Ошибка запроса";
      throw new Error(error);
    }
    if (response.status === 204) {
      return null;
    }
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      return response.json();
    }
    return response.text();
  });
}

function renderProducts() {
  productsTable.innerHTML = "";
  state.products.forEach((product) => {
    const row = document.createElement("tr");
    const statusValue = product.status || "—";
    const statusClass = product.status ? `status-${product.status.toLowerCase()}` : "";
    row.innerHTML = `
      <td><input type="checkbox" class="select-product" data-id="${product.id}" ${state.selectedProducts.has(product.id) ? "checked" : ""}></td>
      <td>${escapeHtml(product.title || "—")}</td>
      <td>${escapeHtml(product.sku)}</td>
      <td>${escapeHtml(product.manufacturer)}</td>
      <td>${escapeHtml(product.search_mode || "—")}</td>
      <td><span class="status ${statusClass}">${escapeHtml(statusValue)}</span></td>
      <td>
        <div class="row-actions">
          <button class="primary" data-action="search" data-id="${product.id}">Поиск</button>
          <button class="ghost" data-action="logs" data-id="${product.id}">Логи</button>
        </div>
      </td>
    `;
    row.addEventListener("click", (event) => {
      if (event.target.closest("button") || event.target.closest("input[type='checkbox']")) return;
      showDetails(product.id);
    });
    productsTable.appendChild(row);
  });
  updateBatchCount();
}

function renderDetails(product, logs = []) {
  if (!product) {
    detailsContainer.innerHTML = '<div class="details-placeholder">Выберите товар, чтобы увидеть изображения и логи</div>';
    return;
  }
  const imageCards = product.images
    .map(
      (img) => {
        const thumbnail = escapeHtml(img.thumbnail_url || img.image_url);
        return `
      <div class="image-card ${img.is_selected ? "selected" : ""}">
        <img src="${thumbnail}" alt="preview" />
        <button class="${img.is_selected ? "ghost" : "primary"}" data-select="${img.id}">
          ${img.is_selected ? "Выбрано" : "Выбрать"}
        </button>
      </div>
    `;
      }
    )
    .join("");

  const logCards = logs
    .map(
      (log) => {
        const provider = escapeHtml(log.provider.toUpperCase());
        const status = escapeHtml(log.status);
        const error = log.error_message ? `<div class="log-error">Ошибка: ${escapeHtml(log.error_message)}</div>` : "";
        const requestPayload = escapeHtml(log.request_payload || "—");
        const responsePayload = escapeHtml(log.response_payload || "—");
        return `
      <div class="log-entry">
        <strong>${provider} • ${status}</strong>
        ${error}
        <div class="log-block"><span>Запрос</span><pre>${requestPayload}</pre></div>
        <div class="log-block"><span>Ответ</span><pre>${responsePayload}</pre></div>
      </div>
    `;
      }
    )
    .join("");

  detailsContainer.innerHTML = `
    <h3>${escapeHtml(product.title || product.sku)}</h3>
    <div class="meta">${escapeHtml(product.manufacturer)}</div>
    <div class="images-grid">${imageCards || '<div class="details-placeholder">Нет изображений</div>'}</div>
    <div class="log-section">
      <h4>Логи</h4>
      ${logCards || '<div class="details-placeholder">Нет логов для отображения</div>'}
    </div>
  `;

  detailsContainer.querySelectorAll("button[data-select]").forEach((button) => {
    button.addEventListener("click", async (event) => {
      event.stopPropagation();
      const imageId = button.dataset.select;
      try {
        const updated = await api(`/api/products/${product.id}/select-image`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ image_id: Number(imageId) }),
        });
        state.products = state.products.map((p) => (p.id === updated.id ? updated : p));
        state.activeProduct = updated;
        const logs = await api(`/api/products/${updated.id}/logs`);
        renderProducts();
        renderDetails(updated, logs);
      } catch (error) {
        alert(error.message);
      }
    });
  });
}

async function loadProducts() {
  try {
    const products = await api("/api/products");
    const previouslySelected = new Set(state.selectedProducts);
    state.products = products;
    state.selectedProducts = new Set(
      products.filter((product) => previouslySelected.has(product.id)).map((product) => product.id)
    );
    renderProducts();
    if (state.activeProduct) {
      const refreshed = products.find((p) => p.id === state.activeProduct.id);
      if (refreshed) {
        const product = await api(`/api/products/${refreshed.id}`);
        const logs = await api(`/api/products/${refreshed.id}/logs`);
        state.activeProduct = product;
        renderDetails(product, logs);
      }
    }
  } catch (error) {
    console.error(error);
  }
}

async function showDetails(productId) {
  try {
    const product = await api(`/api/products/${productId}`);
    const logs = await api(`/api/products/${productId}/logs`);
    state.activeProduct = product;
    renderDetails(product, logs);
  } catch (error) {
    alert(error.message);
  }
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  loginError.textContent = "";
  const body = new URLSearchParams();
  body.append("username", document.getElementById("username").value);
  body.append("password", document.getElementById("password").value);
  body.append("grant_type", "password");
  try {
    const token = await api("/api/login", {
      method: "POST",
      body,
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });
    state.token = token.access_token;
    overlay.classList.remove("visible");
    state.selectedProducts.clear();
    await loadProducts();
  } catch (error) {
    loginError.textContent = error.message;
  }
});

logoutBtn.addEventListener("click", () => {
  state.token = null;
  overlay.classList.add("visible");
  state.selectedProducts.clear();
  renderProducts();
});

createProductForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = {
    sku: document.getElementById("new-sku").value,
    manufacturer: document.getElementById("new-manufacturer").value,
    title: document.getElementById("new-title").value,
    search_mode: document.getElementById("new-mode").value,
  };
  try {
    const product = await api("/api/products", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    state.products = [product, ...state.products];
    renderProducts();
    createProductForm.reset();
  } catch (error) {
    alert(error.message);
  }
});

productsTable.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const id = button.dataset.id;
  const action = button.dataset.action;
  event.stopPropagation();
  if (action === "search") {
    const mode = prompt("Укажите режим поиска (google / openai)", "google");
    if (!mode) return;
    try {
      await api(`/api/products/${id}/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode }),
      });
      await loadProducts();
      showDetails(Number(id));
    } catch (error) {
      alert(error.message);
    }
  }
  if (action === "logs") {
    showDetails(Number(id));
  }
});

productsTable.addEventListener("change", (event) => {
  const checkbox = event.target.closest(".select-product");
  if (!checkbox) return;
  const id = Number(checkbox.dataset.id);
  if (checkbox.checked) {
    state.selectedProducts.add(id);
  } else {
    state.selectedProducts.delete(id);
  }
  updateBatchCount();
});

importForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  importError.textContent = "";
  const file = document.getElementById("import-file").files[0];
  if (!file) {
    importError.textContent = "Выберите файл";
    return;
  }
  const mode = document.getElementById("import-mode").value;
  const form = new FormData();
  form.append("mode", mode);
  form.append("file", file);
  try {
    const products = await api("/api/products/import", {
      method: "POST",
      body: form,
    });
    state.products = [...products, ...state.products];
    renderProducts();
    importWindow.classList.remove("active");
    importForm.reset();
    document.getElementById("file-label").textContent = "Выберите файл Excel";
  } catch (error) {
    importError.textContent = error.message;
  }
});

document.getElementById("import-file").addEventListener("change", (event) => {
  const file = event.target.files[0];
  document.getElementById("file-label").textContent = file ? file.name : "Выберите файл Excel";
});

if (selectAll) {
  selectAll.addEventListener("change", (event) => {
    state.selectedProducts.clear();
    if (event.target.checked) {
      state.products.forEach((product) => state.selectedProducts.add(product.id));
    }
    renderProducts();
    updateBatchCount();
  });
}

credentialsForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  credentialsError.textContent = "";
  credentialsSuccess.textContent = "";
  const payload = {
    current_password: document.getElementById("current-password").value,
    new_username: document.getElementById("new-username").value,
    new_password: document.getElementById("new-password").value,
  };
  try {
    await api("/api/change-credentials", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    credentialsSuccess.textContent = "Данные обновлены";
    credentialsForm.reset();
  } catch (error) {
    credentialsError.textContent = error.message;
  }
});

function setupFloating(windowElement, triggerId) {
  const trigger = triggerId ? document.getElementById(triggerId) : null;
  const closeBtn = windowElement.querySelector("[data-close]");
  if (trigger) {
    trigger.addEventListener("click", () => {
      windowElement.classList.toggle("active");
      updateBatchCount();
    });
  }
  if (closeBtn) {
    closeBtn.addEventListener("click", () => {
      windowElement.classList.remove("active");
    });
  }
  makeDraggable(windowElement);
}

setupFloating(importWindow, "open-import");
setupFloating(userWindow, "open-user");
setupFloating(batchWindow, "open-batch");

batchForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  batchError.textContent = "";
  if (!state.selectedProducts.size) {
    batchError.textContent = "Выберите хотя бы один товар";
    return;
  }
  const mode = document.getElementById("batch-mode").value;
  const query = document.getElementById("batch-query").value || null;
  try {
    await api("/api/products/batch-search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        product_ids: Array.from(state.selectedProducts),
        mode,
        query_override: query,
      }),
    });
    await loadProducts();
    batchWindow.classList.remove("active");
    document.getElementById("batch-query").value = "";
  } catch (error) {
    batchError.textContent = error.message;
  }
});

function makeDraggable(element) {
  element.classList.add("draggable");
  element.style.left = "50%";
  element.style.top = "50%";
  let offsetX = 0;
  let offsetY = 0;
  let isDragging = false;

  element.addEventListener("mousedown", (event) => {
    if (event.target.tagName === "INPUT" || event.target.tagName === "BUTTON" || event.target.tagName === "SELECT") {
      return;
    }
    isDragging = true;
    offsetX = event.clientX - element.offsetLeft;
    offsetY = event.clientY - element.offsetTop;
    element.style.transition = "none";
  });

  document.addEventListener("mousemove", (event) => {
    if (!isDragging) return;
    element.style.left = `${event.clientX - offsetX}px`;
    element.style.top = `${event.clientY - offsetY}px`;
  });

  document.addEventListener("mouseup", () => {
    isDragging = false;
    element.style.transition = "";
  });

  const handle = document.createElement("div");
  handle.className = "resize-handle";
  element.appendChild(handle);

  let isResizing = false;
  let startWidth = 0;
  let startHeight = 0;
  let startX = 0;
  let startY = 0;

  handle.addEventListener("mousedown", (event) => {
    event.stopPropagation();
    isResizing = true;
    startWidth = element.offsetWidth;
    startHeight = element.offsetHeight;
    startX = event.clientX;
    startY = event.clientY;
  });

  document.addEventListener("mousemove", (event) => {
    if (!isResizing) return;
    const newWidth = startWidth + (event.clientX - startX);
    const newHeight = startHeight + (event.clientY - startY);
    element.style.width = `${Math.max(320, newWidth)}px`;
    element.style.height = `${Math.max(220, newHeight)}px`;
  });

  document.addEventListener("mouseup", () => {
    isResizing = false;
  });
}

window.addEventListener("resize", () => {
  renderProducts();
});

function updateBatchCount() {
  if (!batchCount) return;
  batchCount.textContent = state.selectedProducts.size;
  if (selectAll) {
    const total = state.products.length;
    const selected = state.selectedProducts.size;
    selectAll.checked = total > 0 && selected === total;
    selectAll.indeterminate = selected > 0 && selected < total;
  }
}

updateBatchCount();
