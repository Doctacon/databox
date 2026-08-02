import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

const description = document.querySelector<HTMLMetaElement>('meta[name="description"]');
if (description) {
  description.content = "Browser-only Arizona bird watch planner with deterministic sunrise calendar events";
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode><App /></React.StrictMode>,
);
