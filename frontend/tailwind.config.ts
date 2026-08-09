import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Restrained agro-industrial palette — greens used as accents, never gradients.
        moss: {
          50: "#f1f7f2",
          100: "#dcebe0",
          800: "#1e4634",
          900: "#173726",
        },
      },
    },
  },
  plugins: [],
};

export default config;
