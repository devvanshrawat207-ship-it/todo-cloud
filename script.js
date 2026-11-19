// All data lives on the server (see server.py), so tasks are the same on every device.
const API = "/api/todos";

const form = document.getElementById("add-form");
const input = document.getElementById("new-todo");
const list = document.getElementById("list");
const heading = document.getElementById("heading");
const summary = document.getElementById("summary");
const statusEl = document.getElementById("status");
const clearBtn = document.getElementById("clear-done");
const filterBtns = document.querySelectorAll(".filters button");

let todos = [];
let filter = "all";
let focusId = null; // keeps keyboard focus on a task after it re-renders

async function api(path = "", options = {}) {
  let res;
  try {
    res = await fetch(API + path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch {
    throw new Error("Can't reach the server. Check your connection and try again.");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "Something went wrong. Try again.");
  return data;
}

// Runs a server action, shows any error, then redraws the list.
async function run(action) {
  statusEl.textContent = "";
  try {
    await action();
  } catch (err) {
    statusEl.textContent = err.message;
  }
  render();
}

function row(todo) {
  const li = document.createElement("li");
  li.dataset.id = todo.id;
  if (todo.done) li.className = "done";

  const label = document.createElement("label");
  const box = document.createElement("input");
  box.type = "checkbox";
  box.checked = todo.done;
  const text = document.createElement("span");
  text.className = "text";
  text.textContent = todo.text;
  label.append(box, text);

  const del = document.createElement("button");
  del.type = "button";
  del.className = "remove";
  del.textContent = "×";
  del.setAttribute("aria-label", `Delete task: ${todo.text}`);

  li.append(label, del);
  return li;
}

function emptyRow() {
  const li = document.createElement("li");
  li.className = "empty";
  li.textContent = {
    all: "No tasks yet. Type one above and select Add task.",
    active: "Nothing left to do.",
    done: "No completed tasks yet.",
  }[filter];
  return li;
}

function render() {
  const open = todos.filter((t) => !t.done).length;
  const doneCount = todos.length - open;

  heading.textContent = open ? `${open} to do` : todos.length ? "All done" : "Nothing yet";
  summary.textContent = `${doneCount} of ${todos.length} completed`;
  clearBtn.hidden = doneCount === 0;
  filterBtns.forEach((b) =>
    b.setAttribute("aria-pressed", String(b.dataset.filter === filter))
  );

  const visible = todos.filter(
    (t) => filter === "all" || (filter === "active" ? !t.done : t.done)
  );
  list.replaceChildren(...(visible.length ? visible.map(row) : [emptyRow()]));

  if (focusId !== null) {
    list.querySelector(`li[data-id="${focusId}"] input`)?.focus();
    focusId = null;
  }
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  run(async () => {
    todos.push(await api("", { method: "POST", body: JSON.stringify({ text }) }));
    input.value = "";
  });
  input.focus();
});

list.addEventListener("change", (e) => {
  if (!e.target.matches('input[type="checkbox"]')) return;
  const id = Number(e.target.closest("li").dataset.id);
  focusId = id;
  run(async () => {
    const updated = await api(`/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ done: e.target.checked }),
    });
    todos = todos.map((t) => (t.id === id ? updated : t));
  });
});

list.addEventListener("click", (e) => {
  const btn = e.target.closest(".remove");
  if (!btn) return;
  const id = Number(btn.closest("li").dataset.id);
  run(async () => {
    await api(`/${id}`, { method: "DELETE" });
    todos = todos.filter((t) => t.id !== id);
  });
});

document.querySelector(".filters").addEventListener("click", (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;
  filter = btn.dataset.filter;
  render();
});

clearBtn.addEventListener("click", () =>
  run(async () => {
    await api("/completed", { method: "DELETE" });
    todos = todos.filter((t) => !t.done);
  })
);

run(async () => {
  todos = await api();
});
