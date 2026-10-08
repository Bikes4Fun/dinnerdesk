import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App.jsx";
import { WeekProvider } from "./week.jsx";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <WeekProvider>
      <App />
    </WeekProvider>
  </React.StrictMode>,
);
