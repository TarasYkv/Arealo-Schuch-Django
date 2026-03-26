import { Config } from "@remotion/cli/config";

Config.setEntryPoint("./src/index.ts");
Config.setPublicDir("./public");

// Timeout erhöhen für langsame Video-Loads
Config.setDelayRenderTimeoutInMilliseconds(120000); // 2 Minuten statt 28 Sek
