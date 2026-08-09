import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// globals:false (explicit vitest imports) disables RTL's auto-cleanup — do it ourselves.
afterEach(() => cleanup());
