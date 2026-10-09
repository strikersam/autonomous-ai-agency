import { defineConfig, loadEnv, transformWithOxc } from "vite";
import react from "@vitejs/plugin-react";

// Migrated from Create React App (react-scripts 5 is unmaintained and pins
// vulnerable transitive dependencies Dependabot cannot patch). Kept compatible
// with everything that consumed the CRA build:
//   - output stays in build/ with assets under build/static/ (wrangler.jsonc,
//     netlify.toml, Dockerfile.backend and backend/server.py's /static mount);
//   - PUBLIC_URL still sets the base path (GitHub Pages serves /autonomous-ai-agency);
//   - source keeps reading process.env.REACT_APP_* and process.env.PUBLIC_URL,
//     replaced here at build time (not under Vitest, where tests set them).
const ENV_KEYS = ["REACT_APP_BACKEND_URL", "REACT_APP_LANGFUSE_BASE_URL", "REACT_APP_LANGFUSE_HOST"];
const BACKEND = "http://localhost:8001";
const PROXIED = ["/api", "/v1", "/v4", "/runtimes", "/admin/api", "/agent"];

// CRA compiled JSX in .js files; Vite 8 infers the language from the extension,
// so src/**/*.js is transformed as JSX here instead of renaming ~100 files that
// other tooling and tests reference by path.
function jsxInJs() {
  return {
    name: "jsx-in-js",
    enforce: "pre",
    async transform(code, id) {
      if (!/\/src\/.*\.js$/.test(id) || id.includes("node_modules")) return null;
      return transformWithOxc(code, id, { lang: "jsx", jsx: { runtime: "automatic" } });
    },
  };
}

export default defineConfig(({ mode }) => {
  const env = { ...loadEnv(mode, process.cwd(), "REACT_APP_"), ...process.env };
  const publicUrl = (env.PUBLIC_URL || "").replace(/\/$/, "");
  const define = mode === "test" ? {} : Object.fromEntries([
    ["process.env.PUBLIC_URL", JSON.stringify(publicUrl)],
    ...ENV_KEYS.map((k) => [`process.env.${k}`, JSON.stringify(env[k] || "")]),
  ]);
  return {
    plugins: [jsxInJs(), react()],
    base: `${publicUrl}/`,
    define,
    build: { outDir: "build", assetsDir: "static", sourcemap: false },
    // The dev server's dependency scan parses src/ too; tell it .js may hold JSX.
    optimizeDeps: { rolldownOptions: { moduleTypes: { ".js": "jsx" } } },
    server: {
      port: 3000,
      proxy: Object.fromEntries(PROXIED.map((p) => [p, BACKEND])),
    },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: "./src/setupTests.js",
      include: ["src/**/*.test.{js,jsx}"],
      css: false,
    },
  };
});
