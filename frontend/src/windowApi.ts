import { getCurrentWindow } from "@tauri-apps/api/window";

export async function minimizeWindow() {
  try {
    const win = getCurrentWindow();
    await win.minimize();
  } catch (err) {
    console.error("minimize failed", err);
  }
}

export async function closeWindow() {
  try {
    const win = getCurrentWindow();
    await win.close();
  } catch (err) {
    console.error("close failed", err);
  }
}

export async function startWindowDrag() {
  try {
    const win = getCurrentWindow();
    await win.startDragging();
  } catch (err) {
    console.error("startDragging failed", err);
  }
}