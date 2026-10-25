import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

const config = [
  { ignores: [".next/**", "node_modules/**", "next-env.d.ts", "src/data/**"] },
  ...nextCoreWebVitals,
  ...nextTypescript,
  {
    rules: {
      // These effects read browser state (URL, session) once on mount so the server and
      // client render the same markup first. Moving them out of effects would change behaviour.
      "react-hooks/set-state-in-effect": "off",
    },
  },
];

export default config;
