declare namespace NodeJS {
  interface ProcessEnv {
    NEXT_PUBLIC_API_URL: string;
    NEXT_PUBLIC_PYTHON_API_URL: string;
    NESTJS_API_URL: string;
    NODE_ENV: 'development' | 'production' | 'test';
    DATABASE_URL: string;
  }
} 