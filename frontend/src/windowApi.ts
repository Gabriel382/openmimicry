
import { getCurrentWindow } from "@tauri-apps/api/window";

export async function minimizeWindow() {
  try {
    await getCurrentWindow().minimize();
  } catch (err) {
    console.error("minimize failed", err);
  }
}

export async function closeWindow() {
  try {
    await getCurrentWindow().close();
  } catch (err) {
    console.error("close failed", err);
  }
}

export async function startWindowDrag() {
  try {
    await getCurrentWindow().startDragging();
  } catch (err) {
    console.error("startDragging failed", err);
  }
}
