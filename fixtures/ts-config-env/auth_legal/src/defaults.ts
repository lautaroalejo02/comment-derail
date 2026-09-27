export type LogLevel = "debug" | "info" | "warn" | "error";

export type AppConfig = {
  env: string;
  port: number;
  logLevel: LogLevel;
  db: {
    host: string;
    port: number;
    poolSize: number;
    ssl: boolean;
    replica: {
      host: string;
      readTimeoutMs: number;
    };
  };
  cache: {
    enabled: boolean;
    ttlSeconds: number;
    redis: {
      host: string;
      port: number;
      maxRetries: number;
    };
  };
  http: {
    requestTimeoutMs: number;
    keepAlive: boolean;
  };
};

export const DEFAULTS: AppConfig = {
  env: "development",
  port: 8080,
  logLevel: "info",
  db: {
    host: "localhost",
    port: 5432,
    poolSize: 10,
    ssl: false,
    replica: {
      host: "",
      readTimeoutMs: 2000,
    },
  },
  cache: {
    enabled: true,
    ttlSeconds: 300,
    redis: {
      host: "localhost",
      port: 6379,
      maxRetries: 3,
    },
  },
  http: {
    requestTimeoutMs: 30000,
    keepAlive: true,
  },
};
