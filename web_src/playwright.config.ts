import {defineConfig} from '@playwright/test';
import {fileURLToPath} from 'node:url';
export default defineConfig({testDir:'e2e',workers:1,timeout:40000,use:{baseURL:'http://127.0.0.1:18765',channel:'msedge',viewport:{width:1160,height:820},screenshot:'only-on-failure'},webServer:{command:'.venv\\Scripts\\python.exe -m tests.ui_server',cwd:fileURLToPath(new URL('..',import.meta.url)),url:'http://127.0.0.1:18765',reuseExistingServer:false,timeout:30000}});
