import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  use: { baseURL: "http://127.0.0.1:8766", headless: true },
  webServer: {
    command: "python ../scripts/e2e_server.py",
    url: "http://127.0.0.1:8766/api/health",
    reuseExistingServer: true,
    timeout: 30000,
  },
});
