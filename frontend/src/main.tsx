import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { CuraPage } from "./pages/CuraPage";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <CuraPage />
  </StrictMode>
);
