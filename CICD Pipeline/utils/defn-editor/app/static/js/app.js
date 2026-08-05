/* global agGrid */

const state = {
  schema: null,
  ui: [],
  session: null,
  grids: new Map(),
  dirHandle: null,
};

const logEl = document.getElementById("log");
const pathEl = document.getElementById("project-path");
const folderInput = document.getElementById("folder-input");
const folderFallback = document.getElementById("folder-fallback");
const tabBar = document.getElementById("tab-bar");
const panelsEl = document.getElementById("panels");
const btnBrowse = document.getElementById("btn-browse");
const btnLoad = document.getElementById("btn-load");
const btnValidate = document.getElementById("btn-validate");
const btnSave = document.getElementById("btn-save");

function log(message, level = "info") {
  const entry = document.createElement("div");
  entry.className = `log-entry ${level}`;
  entry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
  logEl.prepend(entry);
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || res.statusText);
  }
  return data;
}

function setControlsLoaded(loaded) {
  btnValidate.disabled = !loaded;
  btnSave.disabled = !loaded;
}

function isRowLocked(row) {
  return Boolean(row && row._locked);
}

function stripRowMeta(row) {
  const copy = { ...row };
  delete copy._locked;
  return copy;
}

function prepareLoadedRows(rows) {
  return (rows || []).map((row) => ({ ...row, _locked: true }));
}

function boolEditor() {
  return {
    cellEditor: "agSelectCellEditor",
    cellEditorParams: { values: ["true", "false"] },
    valueFormatter: (p) => String(p.value ?? ""),
  };
}

function columnDefsFor(varDef) {
  const boolCols = new Set(["portfast", "dnac_managed"]);
  return (varDef.columns || []).map((col) => {
    const def = {
      field: col,
      headerName: col,
      editable: (params) => !isRowLocked(params.data),
      flex: 1,
      minWidth: 100,
    };
    if (boolCols.has(col)) {
      Object.assign(def, boolEditor());
      def.editable = (params) => !isRowLocked(params.data);
    }
    if (col === "nac_key") {
      def.cellClass = "sensitive";
    }
    return def;
  });
}

function newRowFromAdjacent(columns, templateRow) {
  const row = { _locked: false };
  if (templateRow) {
    for (const col of columns) {
      row[col] = templateRow[col] ?? "";
    }
    return row;
  }
  for (const col of columns) {
    if (col === "portfast" || col === "dnac_managed") {
      row[col] = "false";
    } else {
      row[col] = "";
    }
  }
  return row;
}

function templateRowForAdd(gridApi) {
  const rows = [];
  gridApi.forEachNode((node) => {
    if (node.data) rows.push(node.data);
  });
  if (!rows.length) return null;

  const selected = gridApi.getSelectedRows();
  if (selected.length) {
    const selectedSet = new Set(selected);
    for (let i = rows.length - 1; i >= 0; i -= 1) {
      if (selectedSet.has(rows[i])) {
        return rows[i];
      }
    }
  }
  return rows[rows.length - 1];
}

function createGrid(container, varDef, rows) {
  const gridId = `${varDef.name}`;
  const columnDefs = columnDefsFor(varDef);
  const gridOptions = {
    columnDefs,
    rowData: prepareLoadedRows(rows),
    defaultColDef: { resizable: true, sortable: true, filter: true },
    rowSelection: { mode: "multiRow", checkboxes: true, headerCheckbox: false },
    stopEditingWhenCellsLoseFocus: true,
    rowClassRules: {
      "row-locked": (params) => isRowLocked(params.data),
    },
    onCellValueChanged: () => syncSessionFromUI(),
  };
  const api = agGrid.createGrid(container, gridOptions);
  state.grids.set(gridId, { api, varDef });
  return api;
}

function buildPanels() {
  tabBar.innerHTML = "";
  panelsEl.innerHTML = "";
  state.grids.clear();

  state.ui.forEach((tab, index) => {
    const tabBtn = document.createElement("button");
    tabBtn.type = "button";
    tabBtn.textContent = tab.name;
    tabBtn.className = index === 0 ? "active" : "";
    tabBtn.dataset.tab = tab.name;
    tabBtn.addEventListener("click", () => activateTab(tab.name));
    tabBar.appendChild(tabBtn);

    const panel = document.createElement("div");
    panel.className = `panel${index === 0 ? " active" : ""}`;
    panel.id = `panel-${tab.name}`;
    panel.dataset.tab = tab.name;

    const fileData = state.session?.files?.[tab.file];
    for (const varDef of tab.variables) {
      const section = document.createElement("section");
      section.className = "section";
      section.dataset.file = tab.file;
      section.dataset.var = varDef.name;

      const title = document.createElement("h2");
      title.textContent = varDef.section || varDef.name;
      section.appendChild(title);

      const hint = document.createElement("p");
      hint.className = "section-hint";
      hint.textContent =
        varDef.binding === "scalar"
          ? "Existing values are read-only. Catalyst Center templates are additive only."
          : "Existing rows are read-only (grey). Add row copies the row above (or last row).";
      section.appendChild(hint);

      const payload = fileData?.variables?.[varDef.name];

      if (varDef.binding === "scalar") {
        const grid = document.createElement("div");
        grid.className = "scalar-grid";
        const label = document.createElement("label");
        label.textContent = varDef.name;
        label.htmlFor = `scalar-${varDef.name}`;
        const input = document.createElement("input");
        input.id = `scalar-${varDef.name}`;
        input.type = "text";
        input.value = payload?.value ?? "";
        input.readOnly = true;
        input.className = "readonly";
        grid.append(label, input);
        section.appendChild(grid);
      } else {
        const toolbar = document.createElement("div");
        toolbar.className = "grid-toolbar";
        const addBtn = document.createElement("button");
        addBtn.type = "button";
        addBtn.textContent = "Add row";
        const delBtn = document.createElement("button");
        delBtn.type = "button";
        delBtn.textContent = "Delete selected (new rows only)";
        toolbar.append(addBtn, delBtn);
        section.appendChild(toolbar);

        const gridHost = document.createElement("div");
        gridHost.className = "ag-theme-quartz";
        section.appendChild(gridHost);

        const rows = payload?.rows || [];
        const gridApi = createGrid(gridHost, varDef, rows);

        addBtn.addEventListener("click", () => {
          const template = templateRowForAdd(gridApi);
          const newRow = newRowFromAdjacent(varDef.columns, template);
          gridApi.applyTransaction({ add: [newRow] });
          syncSessionFromUI();
        });
        delBtn.addEventListener("click", () => {
          const selected = gridApi.getSelectedRows();
          const deletable = selected.filter((row) => !isRowLocked(row));
          if (!selected.length) {
            log("Select new row(s) to delete", "warn");
            return;
          }
          if (!deletable.length) {
            log("Existing rows cannot be deleted", "warn");
            return;
          }
          gridApi.applyTransaction({ remove: deletable });
          syncSessionFromUI();
        });
      }

      panel.appendChild(section);
    }

    panelsEl.appendChild(panel);
  });
}

function activateTab(name) {
  tabBar.querySelectorAll("button").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === name);
  });
  panelsEl.querySelectorAll(".panel").forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.tab === name);
  });
}

function syncSessionFromUI() {
  if (!state.session) return;

  for (const tab of state.ui) {
    const fileData = state.session.files[tab.file];
    if (!fileData) continue;

    for (const varDef of tab.variables) {
      if (varDef.binding === "scalar") {
        continue;
      }

      const entry = state.grids.get(varDef.name);
      if (!entry) continue;
      const rows = [];
      entry.api.forEachNode((node) => {
        if (node.data) rows.push(stripRowMeta(node.data));
      });
      fileData.variables[varDef.name] = {
        type: varDef.binding,
        rows,
      };
    }
  }
}

async function persistSession() {
  syncSessionFromUI();
  await api("/api/session", {
    method: "PUT",
    body: JSON.stringify(state.session),
  });
}

async function loadSchema() {
  const data = await api("/api/schema");
  state.schema = data.schema;
  state.ui = data.ui;
}

function currentFolder() {
  return folderInput.value.trim();
}

async function readDefnFilesFromHandle(dirHandle) {
  const files = {};
  for await (const entry of dirHandle.values()) {
    if (entry.kind !== "file") continue;
    if (!entry.name.startsWith("DEFN-") || !entry.name.endsWith(".j2")) continue;
    const file = await entry.getFile();
    files[entry.name] = await file.text();
  }
  return files;
}

async function writeDefnFilesToHandle(dirHandle, fileMap) {
  for (const [name, content] of Object.entries(fileMap)) {
    const handle = await dirHandle.getFileHandle(name, { create: false });
    const writable = await handle.createWritable();
    await writable.write(content);
    await writable.close();
  }
}

function applyLoadedSession(session, label) {
  state.session = session;
  state.dirHandle = session.load_mode === "browser" ? state.dirHandle : null;
  pathEl.textContent = label || session.project_folder;
  folderInput.value = session.load_mode === "path" ? session.project_folder : label || session.project_folder;
  buildPanels();
  setControlsLoaded(true);
  log(`Loaded ${Object.keys(session.files).length} DEFN files`, "ok");
  log("Existing rows and scalars are read-only — add new rows only", "info");
}

async function loadFromFileMap(files, folderLabel) {
  const session = await api("/api/project/load-files", {
    method: "POST",
    body: JSON.stringify({ files, folder_label: folderLabel }),
  });
  applyLoadedSession(session, folderLabel);
}

async function browseFolder() {
  try {
    const native = await fetch("/api/browse-folder", { method: "POST" });
    const nativeData = await native.json().catch(() => ({}));
    if (native.ok && nativeData.folder) {
      folderInput.value = nativeData.folder;
      state.dirHandle = null;
      log(`Selected ${nativeData.folder}`, "ok");
      return;
    }
  } catch {
    // fall through to browser picker
  }

  if (window.showDirectoryPicker) {
    try {
      const dirHandle = await window.showDirectoryPicker({ mode: "readwrite" });
      const files = await readDefnFilesFromHandle(dirHandle);
      if (!Object.keys(files).length) {
        log("No DEFN-*.j2 files in selected folder", "warn");
        return;
      }
      state.dirHandle = dirHandle;
      await loadFromFileMap(files, dirHandle.name);
      return;
    } catch (err) {
      if (err?.name === "AbortError") return;
      log(err.message || String(err), "error");
      return;
    }
  }

  folderFallback.click();
}

async function onFallbackFolderPicked(event) {
  const picked = Array.from(event.target.files || []);
  event.target.value = "";
  if (!picked.length) return;

  const files = {};
  for (const file of picked) {
    const base = file.name;
    if (!base.startsWith("DEFN-") || !base.endsWith(".j2")) continue;
    files[base] = await file.text();
  }
  if (!Object.keys(files).length) {
    log("No DEFN-*.j2 files in selected folder", "warn");
    return;
  }

  const label = picked[0].webkitRelativePath.split("/")[0] || "picked-folder";
  state.dirHandle = null;
  await loadFromFileMap(files, label);
}

async function reloadCurrentProject() {
  if (state.session?.load_mode === "browser" && state.dirHandle) {
    const files = await readDefnFilesFromHandle(state.dirHandle);
    await loadFromFileMap(files, state.dirHandle.name);
    log("Reloaded — new rows are now locked", "info");
    return;
  }
  if (state.session?.load_mode === "path" && state.session.project_folder) {
    state.session = await api("/api/project/load", {
      method: "POST",
      body: JSON.stringify({ folder: state.session.project_folder }),
    });
    applyLoadedSession(state.session);
    log("Reloaded — new rows are now locked", "info");
  }
}

async function loadProject() {
  const folder = currentFolder();
  if (!folder) {
    log("Enter an absolute project folder path", "warn");
    return;
  }

  btnLoad.disabled = true;
  try {
    state.dirHandle = null;
    state.session = await api("/api/project/load", {
      method: "POST",
      body: JSON.stringify({ folder }),
    });
    applyLoadedSession(state.session);
  } catch (err) {
    log(err.message, "error");
  } finally {
    btnLoad.disabled = false;
  }
}

async function validateProject() {
  try {
    await persistSession();
    const result = await api("/api/validate", { method: "POST" });
    if (!result.issues.length) {
      log("Validation passed", "ok");
      return;
    }
    for (const issue of result.issues) {
      log(issue.message, issue.level === "error" ? "error" : "warn");
    }
  } catch (err) {
    log(err.message, "error");
  }
}

async function saveProject() {
  try {
    await persistSession();
    const result = await api("/api/save", { method: "POST", body: "{}" });
    if (result.load_mode === "browser" && state.dirHandle && result.files) {
      await writeDefnFilesToHandle(state.dirHandle, result.files);
      log(`Wrote ${Object.keys(result.files).length} file(s) to ${state.dirHandle.name}`, "ok");
    } else {
      log(result.message, "ok");
    }
    for (const issue of result.issues || []) {
      log(issue.message, issue.level === "error" ? "error" : "warn");
    }
    await reloadCurrentProject();
  } catch (err) {
    log(err.message, "error");
  }
}

btnBrowse.addEventListener("click", browseFolder);
folderFallback.addEventListener("change", onFallbackFolderPicked);
btnLoad.addEventListener("click", loadProject);
btnValidate.addEventListener("click", validateProject);
btnSave.addEventListener("click", saveProject);

(async function init() {
  try {
    await loadSchema();
    const config = await api("/api/config");
    folderInput.value = config.loaded_folder || config.default_folder || "";
    if (config.allowed_roots?.length) {
      log(`Allowed paths: under ${config.allowed_roots.join(", ")}`, "info");
    }
    if (config.default_folder) {
      pathEl.textContent = config.default_folder;
    }
  } catch (err) {
    log(`Startup failed: ${err.message}`, "error");
  }
})();
