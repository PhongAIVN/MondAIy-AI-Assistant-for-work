import "@/assets/tailwind.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";

const rootEl = document.getElementById("root");
if (!rootEl) {
  throw new Error("Không tìm thấy #root trong options/index.html");
}

createRoot(rootEl).render(
  <StrictMode>
    <App />
  </StrictMode>
);
